import datetime
import json
import requests

from cta_system import get_station, lines, layouts, Pattern

BASE_URL = 'https://lapi.transitchicago.com/api/1.0/ttarrivals.aspx'
API_KEY = '3654e8cbb15840f7b928b2e39da94f1e' # os.getenv('CTA_TRAIN_API_KEY')

def get_arrivals(name=None, map_id=None):
    
    if map_id is not None:
        station = get_station(map_id=map_id)
    elif name is not None:
        station = get_station(name)
    else:
        raise Exception('get_arrivals requires name or map_id')
    
    response = requests.get(f'{BASE_URL}?key={API_KEY}&mapid={station.map_id}&outputType=json')
    if response.status_code != 200:
        raise Exception(f'CTA Web Error {resp.status_code}')
    
    response = json.loads(response.text)
    if response.get('ctatt') is None:
        raise LoggedException(response, 'CTA did not send any arrivals.')

    arrivals = Arrivals(station, response['ctatt'])
    if arrivals.error_code != 0:
        msg = f'CTA API error code {arrivals.error_code}: {arrivals.error_name}'
        raise LoggedException(response, msg)

    return arrivals


class Arrivals:
    def __init__(self, station, ctatt):
        self.station = station
        
        self.timestamp = convert(ctatt, 'tmst', datetime.datetime)        
        self.error_code = convert(ctatt, 'errCd', int)
        self.error_name = convert(ctatt, 'errNm', str)
        
        if self.error_code != 0:
            print(f'API Error {self.error_code}: {self.error_name}')
        
        self.layout = self.get_layout()
        
        # Instead of creating patterns separately, add ETAs to patterns already in layout
        self.add_etas(ctatt)
        print(self.layout)
        # self.patterns = self.get_patterns(ctatt)
    
    def get_layout(self):
        match_layout = [l for l in layouts if l.lines == self.station.lines]
        if not match_layout:
            return
        
        layout = match_layout[0]
        
        # Add non-standard patterns wherever they fit
        # Maybe I should just always put them on a separate page?
        
        # Add ETAs to patterns
        
        
        return layout
    
    def add_etas(self, ctatt):
        lpatterns = self.layout.all_patterns()
        
        # Clear existing ETAs
        for lpattern in lpatterns:
            for eta in lpattern.etas:
                del eta # Didn't work without []; adding to memory?
            lpattern.etas = []
        
        etas = [Eta(e) for e in ctatt.get('eta') or []]
        
        for eta in etas:
            epattern = (eta.line, eta.direction, eta.destination)
            
            for lpattern in lpatterns:
                if epattern == lpattern:
                    lpattern.etas.append(eta)
                    eta.pattern = lpattern
                    break
        
        for lpattern in lpatterns:
            lpattern.etas = sorted(lpattern.etas, key=lambda e: e.minutes_away)
    
    def get_patterns(self, ctatt):
        etas = [Eta(e) for e in ctatt.get('eta') or []]
        
        # Convert to dict by pattern (line, direction, and destination)
        patterns = list(set([(e.line, e.direction, e.destination) for e in etas]))
        return [Pattern(p, etas) for p in patterns]


class Eta:
    def __init__(self, eta):
        self.map_id = convert(eta, 'staId', int)
        self.stop_id = convert(eta, 'stpId', int)
        
        self.run_number = convert(eta, 'rn', int)
        self.line = lines[eta.get('rt')]
        
        self.direction = {None: None, '1': 'North', '5': 'South'}[eta.get('trDr')]
        self.angle = convert(eta, 'heading', int)
        
        dest_id = convert(eta, 'destSt', int)
        if dest_id == 0:
            dest_name = eta.get('destNm')
            
            # Search for station by name
            try:
                self.destination = get_station(dest_name)
            except ValueError:
                
                # Search for non-station destination by name
                try:
                    self.destination = get_station(dest_name, nonstation=True)
                except ValueError:
                    msg = f"Destination with stop_id 0 and unknown name: '{dest_name}' on {self.line.name} Line."
                    log_data(msg)
                    self.destination = get_station('Unknown', nonstation=True)
        else:
            self.destination = get_station(stop_id=dest_id)
        
        # Correct trains into Loop showing opposite terminal
        if self.destination.name != 'Loop':
            if getattr(self.line, f'main_dest_{self.direction.lower()}').name == 'Loop':
                self.destination = get_station('Loop', nonstation=True)
        
        self.is_approaching = convert(eta, 'isApp', bool)
        self.is_scheduled = convert(eta, 'isSch', bool)
        self.is_delayed = convert(eta, 'isDly', bool)
        self.is_faulty = convert(eta, 'isFlt', bool)
        
        self.latitude = convert(eta, 'lat', float)
        self.longitude = convert(eta, 'lon', float)
        
        self.minutes_away = self.get_minutes(eta)
        
        self.pattern = None
    
    def get_minutes(self, eta):
        if self.is_approaching:
            return 0
        
        gen_time = convert(eta, 'prdt', datetime.datetime)
        arr_time = convert(eta, 'arrT', datetime.datetime)
        
        minutes = int(round((arr_time - gen_time).total_seconds() / 60))
        return max(0, minutes)
    
    def get_pattern(self):
        return self.line, self.direction, self.destination
    
    def __str__(self):
        minutes = str(self.minutes_away).rjust(2)
        
        flags = {'S': self.is_scheduled, 'D': self.is_delayed, 'F': self.is_faulty}
        true_flags = ''.join([f[0] for f in flags.items() if f[1]])
        if true_flags:
            minutes += ' ' + true_flags
                
        return minutes.ljust(6)


def convert(_dict, key, data_type):
    """
    Converts string from JSON to new data type
    """
    value = _dict.get(key)
    if value is None:
        return None
    
    if data_type == datetime.datetime:
        return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S')
    elif data_type == bool:
        return bool(int(value))
    else:
        return data_type(value)


class LoggedException(Exception):
    """
    If there's an error parsing the response, save response to file
    """
    def __init__(self, response, message='Error parsing API response.'):
        log = log_data(response)
        self.message = f'{message}\nAPI response has been stored at {log}'
        super().__init__(self.message)


def log_data(data):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if isinstance(data, dict):
        log_path = f'logs/{now}.json'
        with open(log_path, 'w') as file:
            json.dump(data, file, indent=4)
    else:
        print(data)
        log_path = f'logs/{now}.txt'
        with open(log_path, 'w') as file:
            file.write(data)
    
    return log_path