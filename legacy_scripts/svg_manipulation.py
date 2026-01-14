from svgelements import SVG, Path, Shape, Color, Rect

def color_to_opengl_float(c):
    """
    Konvertiert svgelements.Color zu einem Tupel aus Floats (0.0 - 1.0).
    Geeignet für glColor3f(r, g, b).
    """
    if isinstance(c, Color) and c.value is not None:
        # Division durch 255.0 für Normalisierung auf 0.0-1.0
        return (c.red / 255.0, c.green / 255.0, c.blue / 255.0)
    return None

def convertSVGElementsToBytePaths(file_path):
    """
    Converts SVG elements to byte-encoded path strings with their properties.

    Args:
        file_path (str): Path to the SVG file.
    Returns:
        list: A list of dictionaries containing byte-encoded path strings and their properties.
    """
    svg = SVG.parse(file_path)
    
    converted_elements = []

    for element in svg.elements():
        if not isinstance(element, (Path, Shape)):
            continue
            
        if hasattr(element, 'visibility') and element.visibility == 'hidden':
            continue
        
        if isinstance(element, Rect):
            raw_attrs = element.values
            if 'x' not in raw_attrs and 'y' not in raw_attrs:
                if element.width == 1280 and element.height == 720:
                    continue

        try:
            # 1. Create Path object from element
            path_obj = Path(element)
            
            # 2. Apply transformations to get absolute coordinates
            path_obj.reify()

            # 3. Get the 'd' string representation in absolute coordinates
            path_d_string = path_obj.d(relative=False)

            fill_color = element.fill
            stroke_color = element.stroke

            fill_val = color_to_opengl_float(fill_color)
            stroke_val = color_to_opengl_float(stroke_color)

            item = {
                'svg_path_string': path_d_string.encode('utf-8'),
                'fill_color': fill_val, 
                'stroke_color': stroke_val,
                
                'stroke_width': round(element.stroke_width, 2) if element.stroke_width else 0.0,
                'is_filled': fill_val is not None
            }
            
            converted_elements.append(item)
            
        except Exception as e:
            print(f"Error processing an element: {e}")
            continue

    return converted_elements

def float_to_css(vals):
    if vals is None: return "none"
    r = int(vals[0] * 255)
    g = int(vals[1] * 255)
    b = int(vals[2] * 255)
    return f"rgb({r},{g},{b})"

def reconstruct_svg_hardcoded(converted_elements, output_file):
    """
    Reconstructs an SVG file from a list of path data dictionaries.

    Args:
        converted_elements (list): List of dictionaries with path data.
        output_file (str): Path to the output SVG file.
    """
    svg_header = (
        '<svg width="338.67mm" height="190.5mm" '
        'baseProfile="tiny" version="1.2" '
        'viewBox="0 0 1280 720" '
        'xmlns="http://www.w3.org/2000/svg">\n'
    )

    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(svg_header)

            for element in converted_elements:
                d_string = element['svg_path_string'].decode('utf-8')

                fill_str = float_to_css(element['fill_color'])
                stroke_str = float_to_css(element['stroke_color'])
                stroke_width = element['stroke_width']

                f.write(
                    f'  <path d="{d_string}" '
                    f'fill="{fill_str}" '
                    f'stroke="{stroke_str}" '
                    f'stroke-width="{stroke_width}" '
                    f'stroke-linecap="round" stroke-linejoin="round" />\n' 
                )
            
            f.write('</svg>')
            print(f"Test SVG successfully created: {output_file}")

    except Exception as e:
        print(f"Error writing test SVG: {e}")

if __name__ == "__main__":
    svg_path = "tests/svgs/raw_image_0_step_001_drawn.svg"
    converted_elements = convertSVGElementsToBytePaths(svg_path)

    for element in converted_elements:
        for key, value in element.items():
            print(f"{key}: {value}")
        print("-" * 40)

    # Test-SVG for visual verification
    reconstruct_svg_hardcoded(converted_elements, "tests/svgs/test_reconstructed.svg")