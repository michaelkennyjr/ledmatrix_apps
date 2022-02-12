import csv
import json

class Station:
    def __init__(self, data):
        self.name = data.get('name')
        self.lookup_name = data.get('lookup_name') or self.name
        self.other_names = data.get('other_names') or []
        
        if data.get('display_name'):
            self.display_name = data['display_name']
        else:
            self.display_name = self.name[:min(len(self.name), 14)]
        
        if data.get('destination_display'):
            self.destination_display = data['destination_display']
        else:
            self.destination_display = self.name[:min(len(self.name), 7)]
        
        self.map_id = data.get('map_id')
        self.ada = data.get('ada') or False
        self.lines = data.get('lines')
        
        # Flag for non-station destinations
        self.is_nonstation = data.get('is_nonstation') or False
        
    def __str__(self):
        return self.name


class Lines:
    def __init__(self, data):
        self.lines = [Line(i, line) for i, line in enumerate(data)]
        
    def __getitem__(self, item):
        
        # Search line names
        matches = [l for l in self.lines if l.name.lower() == item.lower()]
        if matches:
            return matches[0]
        
        # Search line symbols (abbreviations)
        matches = [l for l in self.lines if item.lower() in [s.lower() for s in l.symbols]]
        if matches:
            return matches[0]
        
        raise KeyError


class Line:
    def __init__(self, i, data):
        self.name = data.get('line')
        self.rgb = data.get('rgb')
        self.order = i
        self.symbols = data.get('symbols') or []
        
        for ns in ['north', 'south']:
            setattr(self, f'main_dest_{ns}', self.get_destination(data.get(f'main_dest_{ns}')))
            setattr(self, f'other_dest_{ns}', self.get_destination(data.get(f'other_dest_{ns}')))
        
    def get_destination(self, dest_id):
        if dest_id is None:
            return []
        
        if isinstance(dest_id, list):
            return [self.get_destination(d) for d in dest_id]
        
        if isinstance(dest_id, int):
            return get_station(map_id=dest_id)
        else:
            return get_station(name=dest_id, nonstation=True)
        
        
    def __str__(self):
        return self.name


class Layout:
    def __init__(self, layout_dict):
        self.lines = [lines[line] for line in layout_dict['lines']]
        self.pages = [LayoutPage(self, page) for page in layout_dict['pages']]
    
    def all_patterns(self):
        patterns = []
        for page in self.pages:
            patterns += [p for p in page.patterns]
        return patterns
    
    def __str__(self):
        lines = ', '.join([line.name for line in self.lines])
        return lines + '\n' + '\n'.join([str(p) for p in self.pages])


class LayoutPage:
    def __init__(self, layout, page_dict):
        self.layout = layout
        self.number = page_dict['page']
        self.patterns = self.get_patterns(page_dict['patterns'])
        
        self.hide = page_dict.get('hide') or []
        self.collapse = page_dict.get('collapse') or []
        self.panels = self.get_panels(page_dict.get('panels'))
    
    def get_patterns(self, pattern_dict):
        patterns = []
        for pattern in pattern_dict:
            line = lines[pattern['line']]
            direction = pattern['direction']
            destination = get_station(map_id=pattern['destination'])
            patterns.append(Pattern((line, direction, destination)))
        
        return patterns
    
    def get_panels(self, panel_dict):
        panels = {}
        
        # Get sign panel colors from layout, if they exist; default to station colors
        for side in ['left', 'right']:
            if panel_dict is None:
                panels[side] = self.layout.lines
            else:
                panels[side] = [lines[l] for l in panel_dict[side]]
        
        return panels
    
    def draw_patterns(self):
        patterns = [p for p in self.patterns if p.etas or self.patterns.index(p) not in self.hide]
        
        # Collapse patterns if applicable/needed
        if self.collapse:
            for collapse_set in self.collapse:
                if len(patterns) == 4:
                    break
                
                subpatterns = [self.patterns[i] for i in collapse_set['subpatterns']]
                if all([p in patterns for p in subpatterns]):
                    for p in subpatterns:
                        patterns.pop(patterns.index(p))
                    
                    idx = min(collapse_set['subpatterns'])
                    collapsed_pattern = CollapsedPattern(subpatterns, collapse_set)
                    patterns.insert(idx, collapsed_pattern)
            
        return patterns
    
    def __str__(self):
        return f'  Page {self.number}\n' + '\n'.join(f'    {str(p)}' for p in self.draw_patterns())


class Pattern:
    def __init__(self, pattern):
        self.line, self.direction, self.destination = pattern
        self.etas = []
                             
    def __eq__(self, other):
        if isinstance(other, Pattern):
            return (self.line, self.direction, self.destination) == (other.line, other.direction, other.destination)
        elif isinstance(other, tuple):
            return (self.line, self.direction, self.destination) == other
        else:
            return False
      
    def __str__(self):
        line = self.line.name.ljust(8)
        direction = self.direction.ljust(8)
        destination = self.destination.destination_display.ljust(7)
        
        return line + direction + destination + '    ' + ''.join(str(e) for e in self.etas)


class CollapsedPattern(Pattern):
    def __init__(self, subpatterns, collapse_set):
        line = lines[collapse_set['line']]
        direction = collapse_set['direction']
        destination = get_station(collapse_set['destination'], nonstation=True)
        
        super().__init__((line, direction, destination))
        
        self.destination_rgb = collapse_set['destination_rgb']
        self.subpatterns = subpatterns
        self.subpattern_rgb = collapse_set['subpattern_rgb']
        
        self.etas = self.get_etas()
        
    def get_etas(self):
        etas = []
        for subpattern in self.subpatterns:
            etas += subpattern.etas
        return sorted(etas, key=lambda e: e.minutes_away)


def get_station(name=None, map_id=None, stop_id=None, nonstation=False):
    
    # Filter out non-station destinations unless argued as True
    station_list = [s for s in stations if s.is_nonstation == nonstation]
    
    if name is not None:
        matches = [s for s in station_list if s.name.lower() == name.lower()]
        if len(matches) > 1:
            raise ValueError(f"Station name '{name}' is ambiguous. Try using the lookup name.")
        if len(matches) == 1:
            return matches[0]
        
        # If not found by name, check lookup_name and other_names
        matches = [s for s in station_list if s.lookup_name.lower() == name.lower()
                   or name.lower() in [n.lower() for n in s.other_names]]
        if matches:
            return matches[0]
        
        raise ValueError(f"Station name '{name}' not found.")
    
    elif map_id is not None:
        if map_id == 'Loop':
            return get_station('Loop', nonstation=True)
        
        matches = [s for s in stations if s.map_id == map_id]
        if matches:
            return matches[0]
        
        raise ValueError(f"Map ID {map_id} not found.")
    
    elif stop_id is not None:
        
        # Find stop ID in stop list from city data portal
        stop = [s for s in stops if s['STOP_ID'] == stop_id]
        if stop:
            stop = stop[0]
        else:
            print([s['STOP_ID'] for s in stops])
            raise ValueError(f"Stop ID {stop_id} not found.")
        
        # Find station that stop ID is assigned to
        matches = [s for s in stations if s.map_id == stop['MAP_ID']]
        if matches:
            return matches[0]
        
        raise ValueError(f"Stop ID {stop_id} does not match any stations.")


def point_to_lines():
    """
    Converts line names to line objects in stations
    """
    for station in stations:
        station.lines = [lines[l] for l in station.lines]


def load_json(resource):
    with open(f'resources/{resource}.json', 'r') as file:
        resource_json = json.load(file)
    return resource_json

[station_json, line_json, layout_json] = [load_json(j) for j in ['stations', 'lines', 'layouts']]
stations = [Station(s) for s in station_json]
lines = Lines(line_json)
layouts = [Layout(l) for l in layout_json]

point_to_lines()
    
with open('resources/CTA_-_System_Information_-_List_of__L__Stops.csv', 'r') as file:
    reader = csv.DictReader(file)
    stops = [row for row in reader]

for stop in stops:
    stop['STOP_ID'] = int(stop['STOP_ID'])
    stop['MAP_ID'] = int(stop['MAP_ID'])