#!/usr/bin/env python3
"""Generate a detailed PDF analysis of the BioSim React Flow architecture."""
from fpdf import FPDF


class AnalysisPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "BioSim React Flow Architecture Analysis", align="R")
        self.ln(4)
        self.set_draw_color(34, 211, 238)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(34, 211, 238)
        self.cell(0, 12, title)
        self.ln(14)

    def subsection_title(self, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(59, 130, 246)
        self.cell(0, 10, title)
        self.ln(12)

    def sub3_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, title)
        self.ln(10)

    def body_text(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, text)
        self.ln(4)

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_text_color(60, 60, 60)
        self.set_fill_color(245, 245, 245)
        x = self.get_x()
        w = self.w - 2 * self.l_margin
        self.multi_cell(w, 5, text, fill=True)
        self.ln(4)

    def bullet(self, text, indent=0):
        x = self.get_x() + indent
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.set_x(x)
        self.cell(5, 6, "-")
        self.multi_cell(0, 6, text)
        self.ln(2)

    def key_value(self, key, value):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(60, 60, 60)
        self.cell(60, 6, key + ":")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 6, value)
        self.ln(2)

    def diagram_box(self, x, y, w, h, label, color=(34, 211, 238)):
        self.set_draw_color(*color)
        self.set_fill_color(color[0], color[1], color[2])
        self.rect(x, y, w, h, "D")
        self.set_xy(x, y + h / 2 - 3)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*color)
        self.cell(w, 6, label, align="C")

    def arrow_right(self, x1, y, x2):
        self.set_draw_color(100, 100, 100)
        self.line(x1, y, x2, y)
        self.line(x2 - 3, y - 2, x2, y)
        self.line(x2 - 3, y + 2, x2, y)

    def arrow_down(self, x, y1, y2):
        self.set_draw_color(100, 100, 100)
        self.line(x, y1, x, y2)
        self.line(x - 2, y2 - 3, x, y2)
        self.line(x + 2, y2 - 3, x, y2)


def generate():
    pdf = AnalysisPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)

    # =========================================================================
    # TITLE PAGE
    # =========================================================================
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(34, 211, 238)
    pdf.cell(0, 15, "BioSim", align="C")
    pdf.ln(18)
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 12, "React Flow Architecture", align="C")
    pdf.ln(10)
    pdf.cell(0, 12, "Deep Dive Analysis", align="C")
    pdf.ln(30)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 8, "Understanding Models, Visualizations,", align="C")
    pdf.ln(8)
    pdf.cell(0, 8, "Parameters, and Data Flow", align="C")
    pdf.ln(30)
    pdf.set_draw_color(34, 211, 238)
    pdf.set_line_width(1)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 8, "Generated: March 2026", align="C")

    # =========================================================================
    # TABLE OF CONTENTS
    # =========================================================================
    pdf.add_page()
    pdf.section_title("Table of Contents")
    toc = [
        ("1.", "System Overview", 3),
        ("2.", "Two React Flow Environments", 4),
        ("3.", "The Model Layer (Python Backend)", 6),
        ("4.", "Config Editor Flow (Flow Environment #1)", 8),
        ("5.", "Wiring Panel Flow (Flow Environment #2)", 11),
        ("6.", "Models in Visualization vs Parameters", 14),
        ("7.", "Data Flow: How Everything Connects", 16),
        ("8.", "Renderers: The Visualization Engine", 19),
        ("9.", "State Management Architecture", 21),
        ("10.", "Complete Data Flow Diagram", 23),
    ]
    for num, title, page in toc:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(12, 8, num)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(140, 8, title)
        pdf.set_font("Helvetica", "", 11)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 8, str(page), align="R")
        pdf.ln(8)

    # =========================================================================
    # 1. SYSTEM OVERVIEW
    # =========================================================================
    pdf.add_page()
    pdf.section_title("1. System Overview")

    pdf.body_text(
        "BioSim is a biological simulation platform with a Python backend and a React "
        "TypeScript frontend (simui-ui). The system has TWO distinct React Flow environments "
        "that serve different purposes. Understanding this distinction is the key to "
        "understanding the architecture."
    )

    pdf.subsection_title("The Two Modes")
    pdf.body_text(
        "The application operates in two modes, controlled by the AppMode type in App.tsx:"
    )
    pdf.bullet('"simulation" mode - The main runtime view with the WiringPanel (React Flow #2)')
    pdf.bullet('"editor" mode - The ConfigEditor view (React Flow #1)')

    pdf.body_text(
        'Users switch between modes using a button in the UI or via URL hash (#editor). '
        'Each mode has its own React Flow canvas with different node types, data models, '
        'and purposes.'
    )

    pdf.subsection_title("Key Architecture Layers")
    pdf.bullet("Python Backend: BioModule base class, ModuleRegistry, simulation engine")
    pdf.bullet("REST API: /api/spec, /api/visuals, /api/editor/*, /api/run, /api/stream (SSE)")
    pdf.bullet("State Management: React Context (UiProvider) with controls, visuals, events")
    pdf.bullet("React Flow #1: ConfigEditor - drag-and-drop module graph builder")
    pdf.bullet("React Flow #2: WiringPanel - runtime wiring visualization")
    pdf.bullet("Renderers: Timeseries, Bar, Table, ImageView, Graph visualizations")

    # =========================================================================
    # 2. TWO REACT FLOW ENVIRONMENTS
    # =========================================================================
    pdf.add_page()
    pdf.section_title("2. Two React Flow Environments")

    pdf.body_text(
        "This is the most important concept to understand. BioSim has TWO completely separate "
        "React Flow canvases, each with different node types, different data models, and "
        "different purposes:"
    )

    pdf.subsection_title("React Flow #1: ConfigEditor")
    pdf.key_value("File", "components/editor/ConfigEditor.tsx")
    pdf.key_value("Node Type", "'moduleNode' -> ModuleNode component")
    pdf.key_value("Purpose", "Build/edit simulation configuration graphs (YAML configs)")
    pdf.key_value("Data Source", "API: /api/editor/modules, /api/editor/config")
    pdf.key_value("When Visible", 'AppMode === "editor" (accessed via #editor hash)')
    pdf.body_text(
        "This is a full graph editor with a module palette on the left, the React Flow canvas "
        "in the center, and a properties panel on the right. Users drag modules from the palette "
        "onto the canvas and connect them via input/output ports. The graph can be saved as YAML "
        "and applied to the running simulation."
    )

    pdf.subsection_title("React Flow #2: WiringPanel")
    pdf.key_value("File", "components/WiringPanel.tsx")
    pdf.key_value("Node Type", "'wiringNode' -> WiringNode component")
    pdf.key_value("Purpose", "Visualize and edit runtime module wiring connections")
    pdf.key_value("Data Source", "UI controls: wiring, module_ports, models JSON controls")
    pdf.key_value("When Visible", 'Inside MainContent when spec has a "wiring" JSON control')
    pdf.body_text(
        "This is an inline, collapsible panel within the simulation view. It reads wiring data "
        "from JSON control values and renders modules as nodes with their input/output ports. "
        "Users can add/remove connections, hide/show modules, and toggle composition modules. "
        "Changes are written back to the JSON controls and sent to the backend on the next run."
    )

    pdf.subsection_title("Key Differences")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(40, 40, 40)
    headers = ["Feature", "ConfigEditor (Flow #1)", "WiringPanel (Flow #2)"]
    col_w = [45, 72, 72]
    pdf.set_fill_color(240, 240, 240)
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, border=1, fill=True, align="C")
    pdf.ln()

    rows = [
        ("Node type", "moduleNode", "wiringNode"),
        ("Data model", "ModuleNodeData", "WiringNodeData"),
        ("Source", "API /editor/*", "JSON controls"),
        ("Layout", "Dagre auto-layout", "Dagre auto-layout"),
        ("Palette", "Full drag-drop palette", "Module checkboxes"),
        ("Properties", "PropertiesPanel sidebar", "None (inline)"),
        ("Persistence", "YAML config files", "JSON in controls + localStorage"),
        ("Color coding", "By category (neuro/eco)", "Uniform styling"),
    ]
    pdf.set_font("Helvetica", "", 9)
    for row in rows:
        for i, cell in enumerate(row):
            pdf.cell(col_w[i], 6, cell, border=1)
        pdf.ln()

    # =========================================================================
    # 3. THE MODEL LAYER
    # =========================================================================
    pdf.add_page()
    pdf.section_title("3. The Model Layer (Python Backend)")

    pdf.body_text(
        '"Models" in BioSim refers to Python classes that extend the BioModule abstract base '
        "class. Each model represents a biological process or component that can be wired "
        "together into a simulation."
    )

    pdf.subsection_title("BioModule Base Class")
    pdf.key_value("File", "src/biosim/modules.py")
    pdf.body_text("Every simulation module must implement this interface:")

    pdf.code_block(
        "class BioModule(ABC):\n"
        "    min_dt: float = 0.0\n"
        "\n"
        "    def setup(config) -> None        # Initialize for a run\n"
        "    def reset() -> None               # Reset to initial state\n"
        "    def advance_to(t) -> None         # ABSTRACT: advance state to time t\n"
        "    def set_inputs(signals) -> None   # Receive input signals\n"
        "    def get_outputs() -> Dict[str, BioSignal]  # ABSTRACT: return outputs\n"
        "    def get_state() -> Dict           # Serializable state\n"
        "    def inputs() -> Set[str]          # Declared input port names\n"
        "    def outputs() -> Set[str]         # Declared output port names\n"
        "    def visualize() -> VisualSpec     # Optional visualization spec"
    )

    pdf.subsection_title("Key Model Concepts")

    pdf.sub3_title("Ports (Inputs & Outputs)")
    pdf.body_text(
        "Each module declares input and output ports. Ports are named connection points "
        "that carry BioSignal data. For example, a neuron module might have an input port "
        "'stimulus' and output ports 'spike_train' and 'membrane_potential'. These port "
        "names appear as handles on the React Flow nodes."
    )

    pdf.sub3_title("Constructor Arguments (args)")
    pdf.body_text(
        "Module constructors accept parameters that configure their behavior. The registry "
        "introspects these via Python's inspect module to extract name, type, default value, "
        "and whether the argument is required. These become the editable properties in the UI."
    )

    pdf.sub3_title("Visualization (visualize())")
    pdf.body_text(
        'Modules can optionally return a VisualSpec ({"render": <type>, "data": <payload>}) '
        "from their visualize() method. This is what produces the charts, tables, and graphs "
        "in the simulation view. The backend calls visualize() on each tick and sends the "
        "results to the frontend via SSE."
    )

    pdf.subsection_title("Module Registry")
    pdf.key_value("File", "src/biosim/simui/registry.py")
    pdf.body_text(
        "The ModuleRegistry discovers and catalogs all available BioModule classes. It uses "
        "Python introspection to extract:"
    )
    pdf.bullet("class_path: The full dotted import path (e.g., 'biosim.packs.neuro.LIFNeuron')")
    pdf.bullet("name: The class name (e.g., 'LIFNeuron')")
    pdf.bullet("category: Grouping like 'neuro', 'ecology', 'custom'")
    pdf.bullet("description: From the class docstring")
    pdf.bullet("inputs/outputs: Port names from inputs()/outputs() methods")
    pdf.bullet("args: Constructor parameter specs (name, type, default, required)")

    pdf.body_text(
        "The registry serializes to JSON via to_json() and is served at /api/editor/modules. "
        "This is what populates the ModulePalette in the ConfigEditor."
    )

    # =========================================================================
    # 4. CONFIG EDITOR FLOW
    # =========================================================================
    pdf.add_page()
    pdf.section_title("4. Config Editor Flow (Flow Environment #1)")

    pdf.body_text(
        "The ConfigEditor is a full-featured graph editor for building simulation configurations. "
        "It lives at components/editor/ConfigEditor.tsx and is shown when the app is in 'editor' mode."
    )

    pdf.subsection_title("Layout: Three-Panel Design")
    pdf.body_text("The editor has a three-column layout:")
    pdf.bullet("LEFT (240px): ModulePalette - draggable list of available modules from registry")
    pdf.bullet("CENTER (flex): React Flow canvas - the main graph editing area")
    pdf.bullet("RIGHT (280px): PropertiesPanel - edit properties of selected node")

    pdf.subsection_title("Node Type: ModuleNode")
    pdf.key_value("File", "components/editor/ModuleNode.tsx")
    pdf.key_value("Registration", "nodeTypes = { moduleNode: ModuleNode }")

    pdf.body_text("Each ModuleNode has this data structure:")
    pdf.code_block(
        "interface ModuleNodeData {\n"
        "  label: string          // Node ID (user-editable)\n"
        "  moduleType: string     // Full class path (e.g., 'biosim.packs.neuro.LIFNeuron')\n"
        "  args: Record<string, unknown>  // Constructor arguments\n"
        "  inputs: string[]       // Input port names\n"
        "  outputs: string[]      // Output port names\n"
        "}"
    )

    pdf.sub3_title("Visual Rendering")
    pdf.body_text("Each node is rendered as a card with:")
    pdf.bullet("Header: Shows the node label (ID) with a colored background based on category")
    pdf.bullet("Subtitle: Shows the class name extracted from moduleType")
    pdf.bullet("Left side: Input port handles (target handles) with port names")
    pdf.bullet("Right side: Output port handles (source handles) with port names")

    pdf.sub3_title("Color Coding by Category")
    pdf.bullet("neuro: Blue/cyan theme (var(--primary))")
    pdf.bullet("ecology: Green theme (#22c55e)")
    pdf.bullet("custom: Purple theme (#a855f7)")

    pdf.subsection_title("ModulePalette")
    pdf.key_value("File", "components/editor/ModulePalette.tsx")
    pdf.body_text(
        "The palette displays all modules from the registry, grouped by category (neuro, ecology, "
        "custom). Each entry shows the module name, input ports, and output ports. Users can:"
    )
    pdf.bullet("Search/filter modules by name or description")
    pdf.bullet("Expand/collapse category groups")
    pdf.bullet("Drag a module onto the canvas to create a new node")
    pdf.body_text(
        "The drag-and-drop uses HTML5 drag events. On drag start, the module type and spec "
        "are stored in the dataTransfer object. On drop, a new node is created with a unique "
        "ID and default empty args."
    )

    pdf.subsection_title("PropertiesPanel")
    pdf.key_value("File", "components/editor/PropertiesPanel.tsx")
    pdf.body_text("When a node is selected, the properties panel shows:")
    pdf.bullet("Node ID: Editable text field (supports rename)")
    pdf.bullet("Module Type: Read-only display of the full class path")
    pdf.bullet("Description: Module docstring (first line)")
    pdf.bullet("Arguments: Dynamic form fields based on the module spec's args")
    pdf.bullet("Ports: Read-only list of input and output ports")
    pdf.bullet("Delete button: Remove the node and all connected edges")

    pdf.sub3_title("Argument Input Types")
    pdf.body_text("The panel dynamically renders appropriate inputs based on arg type:")
    pdf.bullet("bool/boolean: Checkbox input")
    pdf.bullet("Enum-like (has options): Select dropdown")
    pdf.bullet("number/int/float: Text input with numeric parsing")
    pdf.bullet("list/List: Text input with JSON parsing")
    pdf.bullet("Other: Plain text input")

    pdf.subsection_title("Data Conversion Functions")
    pdf.body_text(
        "The ConfigEditor has two critical conversion functions that bridge between the "
        "API's graph format and React Flow's node/edge format:"
    )

    pdf.sub3_title("apiGraphToFlow()")
    pdf.code_block(
        "API ConfigGraph -> React Flow nodes/edges\n"
        "  GraphNode -> Node<ModuleNodeData> (type='moduleNode')\n"
        "  GraphEdge -> Edge (type='smoothstep')"
    )

    pdf.sub3_title("flowToApiGraph()")
    pdf.code_block(
        "React Flow nodes/edges -> API ConfigGraph\n"
        "  Node<ModuleNodeData> -> GraphNode\n"
        "  Edge -> GraphEdge"
    )

    # =========================================================================
    # 5. WIRING PANEL FLOW
    # =========================================================================
    pdf.add_page()
    pdf.section_title("5. Wiring Panel Flow (Flow Environment #2)")

    pdf.body_text(
        "The WiringPanel is an inline, collapsible React Flow canvas embedded in the main "
        "simulation view. Unlike the ConfigEditor which works with YAML config files, the "
        "WiringPanel operates on JSON control values that are part of the simulation's UiSpec."
    )

    pdf.subsection_title("When Does It Appear?")
    pdf.body_text(
        "The WiringPanel only renders when the simulation's UiSpec includes a JSON control "
        'named "wiring". This is checked in MainContent.tsx:'
    )
    pdf.code_block(
        "const hasWiring = Boolean(\n"
        "  state.spec?.controls?.some(\n"
        '    (c) => c.type === "json" && c.name === "wiring"\n'
        "  )\n"
        ")"
    )

    pdf.subsection_title("Four JSON Controls")
    pdf.body_text(
        "The WiringPanel reads from up to four JSON-type controls in the UiSpec. These "
        "controls are hidden from the sidebar's controls panel:"
    )

    pdf.sub3_title('1. "wiring" (required)')
    pdf.body_text(
        'A JSON array of connection objects: [{"from": "module.port", "to": ["other.port"]}]. '
        "This defines which module output ports connect to which input ports."
    )

    pdf.sub3_title('2. "module_ports" (optional)')
    pdf.body_text(
        "A JSON object mapping module aliases to their declared ports: "
        '{"alias": {"inputs": [...], "outputs": [...]}}'
    )

    pdf.sub3_title('3. "wiring_layout" (optional)')
    pdf.body_text(
        'A JSON object with node positions and hidden module list: '
        '{"version": 1, "nodes": {"alias": {"x": 100, "y": 200}}, "hidden_modules": [...]}'
    )

    pdf.sub3_title('4. "models" (optional)')
    pdf.body_text(
        "A JSON array of model composition entries. Each entry has an alias, repo info, etc. "
        "This enables the 'Run Composition' feature where users can toggle which models "
        "are included in the simulation."
    )

    pdf.subsection_title("Node Type: WiringNode")
    pdf.body_text("The WiringNode is simpler than ModuleNode:")
    pdf.code_block(
        "type WiringNodeData = {\n"
        "  label: string      // Module alias\n"
        "  inputs: string[]   // Input port names\n"
        "  outputs: string[]  // Output port names\n"
        "}"
    )

    pdf.body_text("Key differences from ModuleNode:")
    pdf.bullet('Has "+ add" handles (NEW_HANDLE_ID) for creating new ports on-the-fly')
    pdf.bullet("No moduleType, args, or category information")
    pdf.bullet("Uniform styling (no category-based colors)")
    pdf.bullet("Supports dynamic port creation via a modal dialog")

    pdf.subsection_title("Connection Flow")
    pdf.body_text("When users connect two nodes in the WiringPanel:")
    pdf.bullet("If both handles are existing ports: connection is made immediately")
    pdf.bullet('If either handle is "+ add" (NEW_HANDLE_ID): a modal dialog opens')
    pdf.bullet("User enters new port name(s) in the modal")
    pdf.bullet("Port is added to the node's data and to module_ports control")
    pdf.bullet("Edge is created and wiring JSON control is updated")
    pdf.bullet("Changes persist to localStorage for the current run/space/model")

    pdf.subsection_title("Wiring Data Conversion")
    pdf.body_text("The WiringPanel has two conversion functions:")

    pdf.sub3_title("wiringToFlow()")
    pdf.code_block(
        "JSON wiring array + module list + ports -> React Flow nodes/edges\n"
        "  Parses 'module.port' references\n"
        "  Creates nodes for all referenced modules\n"
        "  Creates edges for all from->to connections\n"
        "  Filters out hidden modules"
    )

    pdf.sub3_title("edgesToWiring()")
    pdf.code_block(
        "React Flow edges -> JSON wiring array\n"
        "  Groups edges by source (module.port)\n"
        '  Produces [{from: "src.port", to: ["dst.port", ...]}, ...]'
    )

    pdf.subsection_title("Module Visibility & Composition")
    pdf.body_text("The WiringPanel has two sets of checkboxes:")
    pdf.bullet(
        "Modules (diagram only): Toggle visibility in the React Flow canvas. "
        "Does NOT affect the simulation - purely visual."
    )
    pdf.bullet(
        "Run Composition (affects run): Toggle which model entries are included in the "
        '"models" JSON control. This DOES affect the simulation by adding/removing models.'
    )

    # =========================================================================
    # 6. MODELS IN VISUALIZATION VS PARAMETERS
    # =========================================================================
    pdf.add_page()
    pdf.section_title("6. Models in Visualization vs Parameters")

    pdf.body_text(
        'This section directly answers the question: "which models are displayed in the '
        'visualization and which ones form the parameters?"'
    )

    pdf.subsection_title("Models in VISUALIZATION")
    pdf.body_text(
        "The visualization system is powered by the ModuleVisuals component and the "
        "renderers. Here's the complete data path:"
    )

    pdf.sub3_title("Step 1: Backend generates visuals")
    pdf.body_text(
        "Each BioModule's visualize() method returns VisualSpec objects. These are collected "
        "by the simulation engine and sent to the frontend via SSE (on each tick)."
    )
    pdf.code_block(
        "type VisualSpec = {\n"
        '  render: string              // "timeseries", "bar", "table", "image", "graph"\n'
        "  data: Record<string, any>   // Renderer-specific payload\n"
        "  description?: string        // Optional description\n"
        "}\n"
        "type ModuleVisuals = {\n"
        "  module: string              // Module alias/name\n"
        "  visuals: VisualSpec[]       // Array of visual specs\n"
        "}"
    )

    pdf.sub3_title("Step 2: Frontend receives via SSE or API")
    pdf.body_text(
        "The App.tsx SSE handler processes 'snapshot' and 'tick' messages, calling "
        "actions.setVisuals() to update the UiProvider state."
    )

    pdf.sub3_title("Step 3: MainContent renders modules")
    pdf.body_text(
        "MainContent.tsx uses useModuleNames() and useVisualsByModule() hooks to get the "
        "list of modules and their visuals. It renders a ModuleVisuals component for each "
        "visible module."
    )

    pdf.sub3_title("Step 4: ModuleVisuals renders cards")
    pdf.body_text(
        "For each VisualSpec, a VisualizationCard is rendered. The card looks up the "
        "appropriate renderer from the RENDERERS map:"
    )
    pdf.code_block(
        "const RENDERERS = {\n"
        "  timeseries: Timeseries,   // SVG line charts with axes\n"
        "  bar: Bar,                 // Bar chart renderer\n"
        "  table: Table,             // Tabular data renderer\n"
        "  image: ImageView,         // Image/bitmap renderer\n"
        "  graph: Graph,             // SVG circular graph layout\n"
        "}"
    )

    pdf.body_text(
        "KEY INSIGHT: The models that appear in visualization are determined by which "
        "BioModules return non-None from their visualize() method. A module without "
        "visualize() will not appear in the main content area. The Sidebar's 'Modules' "
        "panel lets users show/hide specific modules."
    )

    pdf.subsection_title("Models as PARAMETERS")
    pdf.body_text(
        "Parameters in BioSim come from two sources, corresponding to the two React Flow "
        "environments:"
    )

    pdf.sub3_title("Source 1: ConfigEditor Arguments")
    pdf.body_text(
        "In the ConfigEditor (Flow #1), each ModuleNode has an 'args' field that holds the "
        "constructor parameters for that BioModule. These are edited via the PropertiesPanel. "
        "When the config is applied, these args are passed to the Python module's __init__()."
    )
    pdf.bullet("Defined by: ModuleRegistry introspection of constructor signatures")
    pdf.bullet("Edited via: PropertiesPanel form fields")
    pdf.bullet("Persisted as: YAML config files")
    pdf.bullet("Applied via: /api/editor/apply endpoint")

    pdf.sub3_title("Source 2: UiSpec Controls")
    pdf.body_text(
        "In the Simulation view, the Sidebar shows 'Controls' - these are UiSpec controls "
        "defined by the backend. They come in two types:"
    )

    pdf.bullet(
        "NumberControl: Numeric parameters like 'duration', 'tick_dt', or module-specific "
        "params like 'predator.birth_rate'. These appear as number inputs in the sidebar."
    )
    pdf.bullet(
        "JsonControl: JSON text parameters like 'wiring', 'models', etc. Most are hidden "
        "from the sidebar (wiring, wiring_layout, module_ports, models) and managed by "
        "the WiringPanel instead."
    )

    pdf.body_text(
        "Module-specific number controls use dot notation (e.g., 'prey.growth_rate'). The "
        "Sidebar groups these under collapsible sections named after the module alias."
    )
    pdf.body_text(
        "All control values are sent as part of the /api/run POST request payload."
    )

    # =========================================================================
    # 7. DATA FLOW
    # =========================================================================
    pdf.add_page()
    pdf.section_title("7. Data Flow: How Everything Connects")

    pdf.subsection_title("A. Initialization Flow")
    pdf.body_text("When the app loads:")
    pdf.bullet("1. ApiProvider wraps the app with the API client")
    pdf.bullet("2. UiProvider initializes state (spec, status, visuals, events, controls)")
    pdf.bullet("3. App.tsx fetches /api/spec to get UiSpec (title, controls, modules, capabilities)")
    pdf.bullet("4. Control defaults are extracted from spec and merged with sessionStorage")
    pdf.bullet("5. SSE connection is established to /api/stream for real-time updates")
    pdf.bullet("6. If editor is enabled (api.editor exists), editor toggle button appears")

    pdf.subsection_title("B. Simulation Run Flow")
    pdf.body_text("When the user clicks 'Run Simulation':")
    pdf.bullet("1. All NumberControl values are collected from state.controls")
    pdf.bullet("2. All JsonControl values are parsed (JSON.parse)")
    pdf.bullet("3. Duration and tick_dt are extracted")
    pdf.bullet("4. POST /api/run with {duration, tick_dt, ...allControls}")
    pdf.bullet("5. Backend starts simulation, sends SSE 'tick' events")
    pdf.bullet("6. Each tick contains: status, visuals[], event")
    pdf.bullet("7. Frontend updates state on each tick -> re-renders visualizations")

    pdf.subsection_title("C. SSE Message Flow")
    pdf.code_block(
        "SSE Message Types:\n"
        "  'snapshot' -> {status, visuals[], events[]}\n"
        "  'tick'     -> {status, visuals[], event}\n"
        "  'event'    -> EventRecord\n"
        "  'status'   -> RunStatus\n"
        "  'heartbeat' -> RunStatus"
    )

    pdf.subsection_title("D. ConfigEditor Flow")
    pdf.body_text("When using the config editor:")
    pdf.bullet("1. GET /api/editor/modules -> ModuleRegistry (populates palette)")
    pdf.bullet("2. GET /api/editor/current -> Current config graph (if available)")
    pdf.bullet("3. User drags modules from palette, connects ports")
    pdf.bullet("4. User edits module arguments in PropertiesPanel")
    pdf.bullet("5. Save: PUT /api/editor/config -> persists YAML")
    pdf.bullet("6. Apply: POST /api/editor/apply -> applies to running simulation")
    pdf.bullet("7. Preview: POST /api/editor/to-yaml -> shows YAML preview")

    pdf.subsection_title("E. Wiring Panel Flow")
    pdf.body_text("When using the wiring panel:")
    pdf.bullet("1. On mount, reads 'wiring' JSON control from state")
    pdf.bullet("2. Parses wiring array, extracts modules and connections")
    pdf.bullet("3. Reads 'module_ports' for declared ports")
    pdf.bullet("4. Reads 'wiring_layout' for saved positions")
    pdf.bullet("5. Reads 'models' for composition entries")
    pdf.bullet("6. Renders React Flow graph")
    pdf.bullet("7. On edge changes, converts back to JSON and updates controls")
    pdf.bullet("8. Changes are included in the next /api/run request")

    # =========================================================================
    # 8. RENDERERS
    # =========================================================================
    pdf.add_page()
    pdf.section_title("8. Renderers: The Visualization Engine")

    pdf.body_text(
        "Renderers are React components that transform VisualSpec data into visual output. "
        "Each renderer type handles a specific visualization format."
    )

    pdf.subsection_title("Timeseries (renderers/Timeseries.tsx)")
    pdf.body_text(
        "Pure SVG line chart renderer. Takes series data with (x, y) points and renders "
        "polylines with axes, ticks, and labels. Supports fullscreen mode."
    )
    pdf.code_block(
        "Input data shape:\n"
        "  { series: [{ name?: string, points: [x, y][] }] }\n"
        "\n"
        "Features:\n"
        "  - Auto-scaling axes\n"
        "  - Multi-series with color differentiation\n"
        "  - Responsive SVG viewBox\n"
        "  - Fullscreen support"
    )

    pdf.subsection_title("Bar (renderers/Bar.tsx)")
    pdf.body_text("Bar chart renderer for categorical data.")

    pdf.subsection_title("Table (renderers/Table.tsx)")
    pdf.body_text("Tabular data renderer for structured output.")

    pdf.subsection_title("ImageView (renderers/ImageView.tsx)")
    pdf.body_text("Image/bitmap renderer for visual data like heatmaps or spatial views.")

    pdf.subsection_title("Graph (renderers/Graph.tsx)")
    pdf.body_text(
        "Lightweight SVG circular graph layout. Positions nodes in a circle and draws "
        "edges between them. Used for network visualizations."
    )
    pdf.code_block(
        "Input data shape:\n"
        "  { nodes: [{ id: string }], edges: [{ source: string, target: string }] }\n"
        "\n"
        "Features:\n"
        "  - Circular layout algorithm\n"
        "  - Auto-positioning based on node count\n"
        "  - Fullscreen support"
    )

    pdf.body_text(
        "IMPORTANT: These renderers in renderers/ are NOT the same as the React Flow graphs. "
        "The Graph renderer is a simple SVG circle layout for visualizing network data. The "
        "React Flow canvases in ConfigEditor and WiringPanel are interactive graph editors."
    )

    # =========================================================================
    # 9. STATE MANAGEMENT
    # =========================================================================
    pdf.add_page()
    pdf.section_title("9. State Management Architecture")

    pdf.subsection_title("UiProvider (React Context)")
    pdf.key_value("File", "app/ui.tsx")
    pdf.body_text("Central state store using React Context + useState. Holds:")

    pdf.code_block(
        "UiState = {\n"
        "  spec: UiSpec | null           // Simulation definition (title, controls, modules)\n"
        "  status: RunStatus | null      // Running, paused, progress, errors\n"
        "  visuals: ModuleVisuals[]      // Current visualization data per module\n"
        "  events: EventRecord[]         // Simulation event log\n"
        "  controls: ControlsState       // Current control values (user inputs)\n"
        "  visibleModules: Set<string>   // Which modules to show in main view\n"
        "}"
    )

    pdf.subsection_title("Key Hooks")

    pdf.sub3_title("useUi()")
    pdf.body_text(
        "Returns { state, actions } from the UiProvider context. Used by almost every component."
    )

    pdf.sub3_title("useModuleNames()")
    pdf.body_text(
        "Returns a deduplicated list of module names from both spec.modules and visuals[].module. "
        "This ensures modules appear in the sidebar even if they haven't produced visuals yet."
    )

    pdf.sub3_title("useVisualsByModule()")
    pdf.body_text(
        "Returns a Map<string, VisualSpec[]> grouping visual specs by module name. "
        "Handles merging visuals for modules that appear multiple times."
    )

    pdf.subsection_title("ConfigEditor State (Local)")
    pdf.body_text(
        "The ConfigEditor manages its own state independently using React Flow's "
        "useNodesState and useEdgesState hooks. It does NOT use UiProvider. "
        "State includes:"
    )
    pdf.bullet("nodes/edges: React Flow graph state")
    pdf.bullet("registry: ModuleRegistry from the API")
    pdf.bullet("selectedNode: Currently selected node for PropertiesPanel")
    pdf.bullet("configPath: Path to the current YAML config file")
    pdf.bullet("meta: Graph metadata (title, description)")
    pdf.bullet("isDirty: Whether unsaved changes exist")

    pdf.subsection_title("WiringPanel State (Hybrid)")
    pdf.body_text(
        "The WiringPanel uses a mix of UiProvider controls and local state:"
    )
    pdf.bullet("Reads from: state.controls.wiring, module_ports, wiring_layout, models")
    pdf.bullet("Writes to: actions.setControls() to update control values")
    pdf.bullet("Local nodes/edges: Managed via useState (not useNodesState)")
    pdf.bullet("Persistence: localStorage for wiring data, keyed by run/space/model ID")

    # =========================================================================
    # 10. COMPLETE DATA FLOW DIAGRAM
    # =========================================================================
    pdf.add_page()
    pdf.section_title("10. Complete Data Flow Diagram")

    pdf.body_text("Below is a text-based architectural diagram showing how all pieces connect:")

    pdf.code_block(
        "                        PYTHON BACKEND\n"
        "    +---------------------------------------------------+\n"
        "    |  BioModule subclasses                              |\n"
        "    |    .advance_to(t)     .get_outputs()               |\n"
        "    |    .set_inputs(sig)   .visualize()                 |\n"
        "    |    .inputs()          .outputs()                   |\n"
        "    +---------------------------------------------------+\n"
        "           |                    |              |\n"
        "    ModuleRegistry        SimEngine        VisualSpecs\n"
        "    (introspection)      (orchestrator)   (per-tick)\n"
        "           |                    |              |\n"
        "    +------+----+         +-----+-----+  +----+----+\n"
        "    | /editor/* |         | /api/run  |  | /api/   |\n"
        "    | endpoints |         | /api/spec |  | stream  |\n"
        "    +------+----+         +-----+-----+  +----+----+\n"
        "           |                    |              |\n"
        "    =======|====================|==============|=====\n"
        "           |          REACT FRONTEND           |\n"
        "           |                    |              |\n"
        "    +------+------+      +-----+------+  +----+-------+\n"
        "    | ConfigEditor |      |  Sidebar   |  | SSE Handler|\n"
        "    | (Flow #1)    |      |  Controls  |  | (App.tsx)  |\n"
        "    +------+------+      +-----+------+  +----+-------+\n"
        "           |                    |              |\n"
        "    +------+------+      +-----+------+  +----+-------+\n"
        "    | ModulePalette|      |  UiProvider |  |  visuals  |\n"
        "    | ModuleNode   |      |  (Context)  |  |  events   |\n"
        "    | Properties   |      +-----+------+  |  status    |\n"
        "    +--------------+            |         +----+-------+\n"
        "                          +-----+------+       |\n"
        "                          | WiringPanel |  +---+--------+\n"
        "                          | (Flow #2)   |  | MainContent|\n"
        "                          +-------------+  +---+--------+\n"
        "                                               |\n"
        "                                        +------+------+\n"
        "                                        |ModuleVisuals|\n"
        "                                        +------+------+\n"
        "                                               |\n"
        "                                     +---------+---------+\n"
        "                                     | Renderers:        |\n"
        "                                     |  Timeseries       |\n"
        "                                     |  Bar   Table      |\n"
        "                                     |  ImageView Graph  |\n"
        "                                     +-------------------+"
    )

    pdf.ln(6)
    pdf.subsection_title("Summary: What Goes Where")

    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 7, "Component", border=1, fill=True, align="C")
    pdf.cell(60, 7, "Shows Models As", border=1, fill=True, align="C")
    pdf.cell(70, 7, "Data Source", border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    summary_rows = [
        ("ConfigEditor Flow", "Draggable graph nodes", "/api/editor/modules"),
        ("  ModulePalette", "Categorized list", "ModuleRegistry"),
        ("  ModuleNode", "Node with ports", "ModuleNodeData"),
        ("  PropertiesPanel", "Editable params", "ModuleSpec.args"),
        ("WiringPanel Flow", "Wiring diagram", "JSON controls"),
        ("  WiringNode", "Node with ports", "WiringNodeData"),
        ("  Composition", "Toggleable list", "'models' control"),
        ("Sidebar Controls", "Number inputs", "UiSpec.controls"),
        ("  Module params", "Grouped by alias", "alias.param_name"),
        ("MainContent", "Visual cards", "ModuleVisuals[]"),
        ("  Timeseries", "Line charts", "VisualSpec.data"),
        ("  Bar/Table/etc", "Various charts", "VisualSpec.data"),
        ("  Graph renderer", "Circle SVG", "VisualSpec.data"),
    ]
    for row in summary_rows:
        for i, cell in enumerate(row):
            w = [60, 60, 70][i]
            pdf.cell(w, 6, cell, border=1)
        pdf.ln()

    pdf.ln(8)
    pdf.body_text(
        "This document covers the complete React Flow architecture of BioSim. The key "
        "takeaway is that models appear in THREE distinct contexts: (1) as interactive nodes "
        "in the ConfigEditor for building simulation configurations, (2) as wiring nodes in "
        "the WiringPanel for connecting module ports at runtime, and (3) as visualization "
        "cards in the MainContent area showing real-time simulation output via renderers."
    )

    # Save
    pdf.output("/home/user/biosim/biosim_react_flow_analysis.pdf")
    print("PDF generated: /home/user/biosim/biosim_react_flow_analysis.pdf")


if __name__ == "__main__":
    generate()
