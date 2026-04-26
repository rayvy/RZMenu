# RZMenu/qt_editor/widgets/lib/gl_support.py
"""
Viewport rendering optimization utilities for RZMenu.

IMPORTANT: Direct QOpenGLWidget inside Blender's process causes an
EXCEPTION_ACCESS_VIOLATION in nvoglv64.dll because Blender owns the
primary OpenGL context (used for its own 3D viewport). Creating a
competing Qt OpenGL context in the same process derails the driver.

Safe alternative: configure QGraphicsView render hints and caching
flags that minimise CPU work without touching the OpenGL context.
This gives most of the benefit (batched compositing, reduced repaints)
with zero crash risk.
"""
from PySide6 import QtWidgets, QtGui, QtCore


def try_init_opengl_viewport(view: QtWidgets.QGraphicsView) -> bool:
    """
    Apply safe GPU-friendly rendering configuration to *view*.

    What this does:
    - Enables SmoothPixmapTransform at the view level (bilinear filtering
      for all pixmap draws, matches the in-game cheap texture filter).
    - Sets BoundingRectViewportUpdate: Qt only repaints items whose
      bounding rect intersects the dirty region, reducing repaint area
      dramatically on large scenes when only a few elements move.
    - Uses cached background: the grid/background is rendered once into
      a cache and only invalidated when the scene background actually
      changes, not on every item update.
    - Does NOT create a QOpenGLWidget — avoids the nvoglv64.dll
      context conflict with Blender's own OpenGL renderer.

    Returns:
        True always (configuration always succeeds).
    """
    try:
        # Bilinear filtering for pixmaps — matches in-game cheap filter
        view.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing |
            QtGui.QPainter.RenderHint.SmoothPixmapTransform
        )

        # BoundingRectViewportUpdate: only repaint the bounding rect of
        # changed items. On large scenes with 100+ static elements this
        # means moving one element only repaints that element's area,
        # not the entire viewport — critical for performance.
        view.setViewportUpdateMode(
            QtWidgets.QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )

        # CacheBackground: render the grid/background once into a pixmap
        # and reuse it. Background only re-renders on explicit
        # scene.invalidate(QGraphicsScene.BackgroundLayer) calls.
        view.setCacheMode(
            QtWidgets.QGraphicsView.CacheModeFlag.CacheBackground
        )

        print("[RZMenu] Viewport: Optimized rendering enabled "
              "(bilinear, BoundingRect updates, background cache).")
        return True

    except Exception as e:
        print(f"[RZMenu] Viewport: Render optimization failed, using defaults. ({e})")
        return False
