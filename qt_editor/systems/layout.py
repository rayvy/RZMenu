# RZMenu/qt_editor/systems/layout.py

class GridSolver:
    @staticmethod
    def calculate_layout(container_data, children_count, children_sizes):
        """
        Calculates local coordinates for children within a container.
        
        Args:
            container_data (dict): Contains 'width', 'grid_padding', 'grid_gap', 'grid_cell_size', 'grid_cols'.
            children_count (int): Number of children to arrange.
            children_sizes (list): List of (width, height) tuples for each child.
            
        Returns:
            list: List of (x, y) coordinates relative to the TOP-LEFT of the container's visual rect.
        """
        width = container_data.get('width', 100)
        padding = container_data.get('grid_padding', 0)
        gap = container_data.get('grid_gap', 0)
        cell_size = container_data.get('grid_cell_size', 50)
        cols = container_data.get('grid_cols', 0)

        results = []
        current_x = padding
        current_y = padding
        
        col_counter = 0
        
        for i in range(children_count):
            # Record current placement position
            results.append((current_x, current_y))
            
            # Use specific child size if available, otherwise default to cell_size
            child_w, child_h = children_sizes[i] if i < len(children_sizes) else (cell_size, cell_size)
            
            # Prepare for next item
            col_counter += 1
            
            # Determine if we should wrap to the next row
            wrap = False
            if cols > 0:
                if col_counter >= cols:
                    wrap = True
            else:
                # Auto-flow based on available container width
                next_w = children_sizes[i+1][0] if i+1 < children_count else cell_size
                if current_x + child_w + gap + next_w > width - padding:
                    wrap = True
            
            if wrap:
                current_x = padding
                # Move Y down by the height of the current row (simplified to current child height + gap)
                current_y += child_h + gap
                col_counter = 0
            else:
                current_x += child_w + gap
                
        return results

