import json
import os
import sys

os.chdir(os.path.dirname(__file__))

sys.path.insert(0, '..')
from ledmatrix.ledmatrix import ledmatrix
from ledmatrix.ledmatrix.shape import Box, Line, Text

from arrivals import get_arrivals
from cta_system import lines, stations, get_station, Pattern, CollapsedPattern

STATION = 'State/Lake'

# BIG PROBLEM: THESE FUNCTIONS ARE CALLED AS THEY'RE WRITTEN, WITHOUT CALLING
# Need to add another level of wrapping if I want to use args

color_heights = {
    1: [(0, 6)],
    2: [(0, 2), (4, 6)],
    3: [(0, 1), (2, 4), (5, 6)],
    4: [(0, 1), (2, 3), (4, 5), (6, 6)],
    5: [(0, 0), (1, 2), (3, 3), (4, 5), (6, 6)],
    6: [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 6)]
}


@ledmatrix(refresh_time=5)
def draw_arrivals(canvas):
    def draw_sign(canvas, arrivals):
        """
        Draw gray center of station sign and station name (at startup)
        """
        # Quincy Easter egg
        if arrivals.station.name == 'Quincy':
            Box(canvas, (0, 0), (6, 63), rgb='d4692c', name='outline')
            Box(canvas, (1, 1), (5, 62), rgb='252f52', name='sign_gray')
            Text(canvas, (5, 31), 'QUINCY', align='center', name='sign_text')
        else:
            Box(canvas, (0, 7), (6, 56), rgb='2b2d2e', name='sign_gray')
            Text(canvas, (5, 31), arrivals.station.display_name, align='center', name='sign_text')
            
            draw_panels(canvas, page.panels)
    
    def draw_panels(canvas, panels):
        """
        Draw colored panels on sides of station sign (either at startup or when changed)
        """
        for side in ['left', 'right']:
            # If redrawing, clear previous panels
            if canvas.frame > 0:
                for i in range(6):
                    canvas.destroy(f'panel_{side}_{i}')
                canvas.destroy(f'panel_{side}_white')
            
            rows = color_heights[len(panels[side])]
            cols = {'left': (0, 6), 'right': (57, 63)}[side]
            
            for i, line in enumerate(panels[side]):
                Box(canvas, (rows[i][0], cols[0]), (rows[i][1], cols[1]), rgb=line.rgb,
                    name=f'panel_{side}_{i}')
            
            # Draw white line if exactly two line colors (not enough space for > 2)
            if len(panels[side]) == 2:
                Line(canvas, (3, cols[0]), (3, cols[1]), rgb='ffffff', name=f'panel_{side}_white')
    
    def delete_drawn_arrivals(canvas):
        """
        Delete shapes representing drawn destinations/ETAs so new data can be drawn
        """
        for i in range(4):
            canvas.destroy(f'dest_{i}')
            for j in range(7):
                canvas.destroy(f'dest_{i}_{j}')
                canvas.destroy(f'eta_{i}_{j}')
                
    def draw_patterns(canvas, page):
        """
        Draw the name of each destination and its ETAs
        """
        for i, pattern in enumerate(page.draw_patterns()):
            # Draw collapsed patterns (e.g., "63/A/C") one character at a time (varying RGB)
            if isinstance(pattern, CollapsedPattern):
                col0 = 2
                for j, char in enumerate(pattern.destination.name):
                    draw_char = Text(
                        canvas,
                        (12 + 6 * i, col0),
                        text=char,
                        rgb=pattern.destination_rgb[j],
                        name=f'dest_{i}_{j}'
                    )
                    col0 += draw_char.width + 1
            
            # Destination name (not collapsed)
            else:
                Text(
                    canvas,
                    (12 + 6 * i, 2),
                    text=pattern.destination.destination_display,
                    rgb=pattern.line.rgb,
                    name=f'dest_{i}'
                )
            
            # ETAs for this pattern
            for j, eta in enumerate(pattern.etas[:max(len(pattern.etas), 3)]):
                if eta.is_scheduled:
                    rgb = '2b2d2e' # Make scheduled ETAs gray (they're mostly useless)
                else:
                    if isinstance(pattern, CollapsedPattern): # Color-code for collapsed patterns
                        idx = pattern.subpatterns.index(eta.pattern)
                        rgb = pattern.subpattern_rgb[idx]
                    else:
                        rgb = pattern.line.rgb # Otherwise, use same color as line
                
                Text(
                    canvas,
                    (12 + 6 * i, 39 + 11 * j),
                    text=eta.minutes_away,
                    rgb=rgb,
                    align='right',
                    name=f'eta_{i}_{j}'
                )
    
    # Make an API request to get arrival data
    try:
        arrivals = get_arrivals(STATION)
    except ConnectionError:
        return
    
    # Flip page if more than one page
    page_count = len(arrivals.layout.pages)
    page = arrivals.layout.pages[canvas.frame % page_count]
    
    if canvas.frame == 0:
        draw_sign(canvas, arrivals)
    
    # If sign panels change, redraw
    elif not all([p.panels == page.panels for p in arrivals.layout.pages]):
        draw_panels(canvas, page.panels)

    # Delete arrival text to make way for new data
    delete_drawn_arrivals(canvas)
    
    # Draw each pattern on this page and its ETAs
    draw_patterns(canvas, page)