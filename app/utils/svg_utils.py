from scour import scour
from svgelements import SVG, Path, Shape, Rect
from app.utils.math_utils import float_to_css, color_to_opengl_float
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtCore import QSize, QRect
from PyQt6.QtWidgets import QGraphicsTextItem, QGraphicsPathItem
from PyQt6.QtGui import QPainter, QPainterPath, QFontMetrics, QPen, QBrush
from PyQt6.QtCore import Qt


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

def generateSVGfromDrawing(save_path, background, background_item, scene):
    gen = QSvgGenerator()
    gen.setResolution(96)
    gen.setFileName(str(save_path))
    gen.setSize(QSize(background.width(), background.height()))                       
    scene_rect = scene.sceneRect()
    gen.setViewBox(QRect(int(scene_rect.x()), int(scene_rect.y()), int(scene_rect.width()), int(scene_rect.height())))    
    gen.setTitle("Vektor-Editor Export")
    gen.setDescription("SVG export from PyQt6 QGraphicsScene")

    # For text to path conversion
    temp_path_items = []
    original_text_items = []

    for item in list(scene.items()):
        if isinstance(item, QGraphicsTextItem) and item.isVisible() and item.toPlainText().strip():
            # 1. Copy properties
            font = item.font()
            text = item.toPlainText()
            color = item.defaultTextColor()
            z_value = item.zValue()

            # 2. Create raw path from text
            raw_path = QPainterPath()
            fm = QFontMetrics(font)
            baseline_offset = fm.ascent()
            raw_path.addText(0, baseline_offset, font, text)

            # Apply the item's transformation to get absolute coordinates
            transform_matrix = item.sceneTransform()
            
            # map() applies the matrix to every point in the path
            absolute_path = transform_matrix.map(raw_path)

            # 3. Create PathItem with the absolute path
            path_item = QGraphicsPathItem(absolute_path)
            path_item.setPen(QPen(Qt.PenStyle.NoPen)) 
            path_item.setBrush(QBrush(color))
            
            # The item itself is now at 0,0, because the coordinates are shifted within the path itself.
            path_item.setPos(0, 0) 
            
            # Maintain the original z-value
            path_item.setZValue(z_value)

            # 4. Perform the swap
            scene.addItem(path_item)
            item.hide()
            
            temp_path_items.append(path_item)
            original_text_items.append(item)

    painter = QPainter(gen)

    # 1) Fill the background with black, to ensure that the projected image has a transparent background
    painter.fillRect(scene.sceneRect(), Qt.GlobalColor.black)
    # 2) Temporarily hide the background item to prevent it from being painted
    background_item.setVisible(False)

    # 3) Deselect all selected items to avoid rendering selection frames
    if scene.selectedItems():
        for it in list(scene.selectedItems()):
            it.setSelected(False)

    # 4) Render the scene (now only draws your shapes)
    scene.render(painter)

    painter.end()

    # 5) Restore the background item
    background_item.setVisible(True)
    print(f"Saved SVG: {save_path}")

def optimizeSVG(svg_file_path):
    with open(svg_file_path, "r", encoding="utf-8") as f:
        original_svg_code = f.read()

    options = scour.sanitizeOptions()
    options.remove_metadata        = False
    options.remove_titles          = False
    options.remove_descriptions    = False
    options.keep_editor_data       = True
    options.keep_unreferenced_defs = True
    options.enable_viewboxing      = False
    options.enable_id_stripping    = False
    options.shorten_ids            = False
    options.indent_type            = "space"
    options.nindent                = 1

    optimized_svg_code = scour.scourString(original_svg_code, options)

    with open(svg_file_path, "w", encoding="utf-8") as f:
        f.write(optimized_svg_code)

    print(f"SVG reduced from {len(original_svg_code)} to {len(optimized_svg_code)} bytes")