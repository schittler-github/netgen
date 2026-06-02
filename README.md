# Graph Editor

A simple Python desktop application for editing node-link graphs on a grid.

## Features

- Drag a node from the palette into the canvas to create a new node.
- Left-drag nodes to reposition them.
- Right-drag from one node to another to create directed edges.
- Save the graph structure as JSON.
- Export a basic Gremlin script for the graph.

## Requirements

- Python 3
- Tkinter (usually included with Python)

On Debian/Ubuntu systems, install the Tkinter runtime with:

```bash
sudo apt-get install python3-tk
```

## Run

From the `graph_editor` folder:

```bash
python graph_editor.py
```

## Export formats

- `Save JSON` writes node and edge data to a `.json` file.
- `Export Gremlin` writes a basic Gremlin script to a `.gremlin` or text file.
