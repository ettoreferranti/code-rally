"""
Quick visualization script to preview generated point-to-point rally stages.

Usage:
    python visualize_track.py [seed] [difficulty]

Examples:
    python visualize_track.py
    python visualize_track.py 42 hard
    python visualize_track.py 123 easy
"""

import sys
import math
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from app.core.track import TrackGenerator, SurfaceType


def visualize_track(seed=None, difficulty="medium"):
    """
    Generate and visualize a track.

    Args:
        seed: Random seed (optional)
        difficulty: Track difficulty (easy, medium, hard)
    """
    # Generate track
    generator = TrackGenerator(seed=seed)
    track = generator.generate(difficulty=difficulty)

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # Color map for surfaces
    surface_colors = {
        SurfaceType.ASPHALT: '#404040',
        SurfaceType.WET: '#2a4d6e',
        SurfaceType.GRAVEL: '#8b7355',
        SurfaceType.ICE: '#b0e0e6'
    }

    # Draw each segment
    for i, segment in enumerate(track.segments):
        if segment.is_straight():
            # Draw straight segment
            x_points = [segment.start.x, segment.end.x]
            y_points = [segment.start.y, segment.end.y]
        else:
            # Draw bezier curve
            x_points = []
            y_points = []

            for j in range(51):  # 50 segments for smooth curve
                t = j / 50.0
                x, y = generator._bezier_point(
                    (segment.start.x, segment.start.y),
                    segment.control1,
                    segment.control2,
                    (segment.end.x, segment.end.y),
                    t
                )
                x_points.append(x)
                y_points.append(y)

        # Get color based on surface type
        color = surface_colors.get(segment.start.surface, '#404040')

        # Draw centerline
        ax.plot(x_points, y_points, color=color, linewidth=3, label=f'Segment {i}')

        # Draw track boundaries (simplified - just wider lines)
        ax.plot(x_points, y_points, color=color, linewidth=segment.start.width/5, alpha=0.3)

    # Draw checkpoints
    for checkpoint in track.checkpoints:
        x, y = checkpoint.position

        # Draw checkpoint as a line perpendicular to track
        length = checkpoint.width / 2
        angle = checkpoint.angle + math.pi / 2  # Perpendicular

        x1 = x + length * math.cos(angle)
        y1 = y + length * math.sin(angle)
        x2 = x - length * math.cos(angle)
        y2 = y - length * math.sin(angle)

        ax.plot([x1, x2], [y1, y2], 'r-', linewidth=2, alpha=0.5)
        ax.plot(x, y, 'ro', markersize=6)

    # Draw start position
    start_x, start_y = track.start_position
    ax.plot(start_x, start_y, 'g*', markersize=20, label='Start')

    # Draw start heading arrow
    arrow_length = 100
    arrow_x = arrow_length * math.cos(track.start_heading)
    arrow_y = arrow_length * math.sin(track.start_heading)
    ax.arrow(start_x, start_y, arrow_x, arrow_y,
             head_width=30, head_length=40, fc='green', ec='green', alpha=0.7)

    # Draw finish position (for point-to-point rally stages)
    finish_x, finish_y = track.finish_position
    ax.plot(finish_x, finish_y, 'r*', markersize=20, label='Finish')

    # Draw finish heading arrow
    finish_arrow_x = arrow_length * math.cos(track.finish_heading)
    finish_arrow_y = arrow_length * math.sin(track.finish_heading)
    ax.arrow(finish_x, finish_y, finish_arrow_x, finish_arrow_y,
             head_width=30, head_length=40, fc='red', ec='red', alpha=0.7)

    # Labels and title
    ax.set_xlabel('X Position', fontsize=12)
    ax.set_ylabel('Y Position', fontsize=12)
    title = f'Rally Stage - {difficulty.capitalize()} Difficulty'
    if seed is not None:
        title += f' (seed={seed})'
    ax.set_title(title, fontsize=14, fontweight='bold')

    # Add legend for surfaces
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color=surface_colors[SurfaceType.ASPHALT], lw=4, label='Asphalt'),
        Line2D([0], [0], color=surface_colors[SurfaceType.WET], lw=4, label='Wet'),
        Line2D([0], [0], color=surface_colors[SurfaceType.GRAVEL], lw=4, label='Gravel'),
        Line2D([0], [0], color=surface_colors[SurfaceType.ICE], lw=4, label='Ice'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='r', markersize=8, label='Checkpoints'),
        Line2D([0], [0], marker='*', color='w', markerfacecolor='g', markersize=12, label='Start'),
        Line2D([0], [0], marker='*', color='w', markerfacecolor='r', markersize=12, label='Finish')
    ]
    ax.legend(handles=legend_elements, loc='upper right')

    # Add track info
    info_text = f'Segments: {len(track.segments)}\n'
    info_text += f'Checkpoints: {len(track.checkpoints)}\n'
    info_text += f'Length: {track.total_length:.0f} units'
    ax.text(0.02, 0.98, info_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()

    # Save to file
    filename = f'rally_stage_{difficulty}'
    if seed is not None:
        filename += f'_seed{seed}'
    filename += '.png'

    plt.savefig(filename, dpi=150, bbox_inches='tight')
    print(f'Rally stage visualization saved to: {filename}')

    # Close the figure
    plt.close()


if __name__ == '__main__':
    # Parse command line arguments
    seed = None
    difficulty = "medium"

    if len(sys.argv) > 1:
        try:
            seed = int(sys.argv[1])
        except ValueError:
            difficulty = sys.argv[1]

    if len(sys.argv) > 2:
        difficulty = sys.argv[2]

    # Generate and visualize
    print(f'Generating {difficulty} track...')
    if seed is not None:
        print(f'Using seed: {seed}')

    visualize_track(seed=seed, difficulty=difficulty)
