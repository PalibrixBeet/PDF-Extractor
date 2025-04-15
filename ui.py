import re
import os
import tkinter as tk
from idlelib.configdialog import VerticalScrolledFrame
from tkinter import filedialog, ttk, messagebox, StringVar, IntVar, BooleanVar
from utils import folder_info, define_file
from pathlib import Path

from settings import Settings


def get_user_data():
    """
    Prompt user for PDF processing parameters through command line interface.

    Returns:
        dict: Parameters for PDF reader configuration
    """
    path, files = folder_info()
    pdf_path = define_file(path, files)

    pdf_name = re.split(r'\\', pdf_path)[-1]
    output_path = re.sub(r'\.pdfl'
                         , '.json', pdf_name)

    start_page = int(input('Start page number (skip to start of PDF):\n'
                           '\tInput PDF pages in native order (e.g. page 1 will have index of 1)') or 1)
    end_page = int(input('End page number (skip to end of PDF):\n') or 0)
    skip_pages = input('Pages to skip, separated by comma (skip to none):\n')
    skip_pages = [int(page.strip()) for page in skip_pages.strip().split(',')] if skip_pages else []

    while True:
        _mode = input('PDF pages mode (c - columns, r - rows):\n')
        if _mode in ('c', 'r'):
            break
        print('Invalid mode. Please try again.')

    dehyphenate = input('Remove hyphens (y/n)?\n') in ('y', 'Y', 't', 'T', '1')

    pdf_header = input('PDF header coordinates: ') or None
    pdf_footer = input('PDF footer coordinates: ') or None
    pdf_left = input('PDF left coordinates: ') or None
    pdf_right = input('PDF right coordinates: ') or None

    borders = [pdf_header, pdf_left, pdf_right, pdf_footer]
    return {'pdf_path': pdf_path,
            'output_path': output_path,
            'start_page': start_page,
            'end_page': end_page,
            'skip_pages': skip_pages,
            'dehyphenate': dehyphenate,
            '_mode': _mode,
            'borders': borders}


def get_user_data_debug():
    """
    Provide predefined debug parameters without user input.

    Returns:
        dict: Parameters for PDF reader configuration
    """
    # Example hardcoded path - for debugging only
    pdf_path = r'C:\Users\palib\Programming\Work\Scraping\Scrapy\storage\whole_lines_test.pdf'

    output_path = 'debug.jsonl'

    start_page = 1
    end_page = 10
    skip_pages = []

    _mode = 'r'

    dehyphenate = 'y'

    borders = [None, None, None, None]
    return {'pdf_path': pdf_path,
            'output_path': output_path,
            'start_page': start_page,
            'end_page': end_page,
            'skip_pages': skip_pages,
            'dehyphenate': dehyphenate,
            '_mode': _mode,
            'borders': borders}


class PDFReaderGUI:
    """
    Graphical user interface for the PDF Reader application.
    """

    def __init__(self, root):
        """
        Initialize the GUI.

        Args:
            root: The tkinter root window
        """
        self.style = ttk.Style()
        self.style.configure(".", focuscolor=self.style.configure(".")["background"])

        # For critical widgets where you want to completely disable focus indicators
        self.root = root
        self.root.title("PDF Reader")
        self.root.geometry("700x750")

        self.settings = Settings()

        # Initialize variables
        self.pdf_path_var = StringVar()
        self.output_path_var = StringVar()
        self.extract_filetype_var = StringVar(value=self.settings.get_setting('extract_filetype', 'jsonl'))
        self.start_page_var = IntVar(value=self.settings.get_setting("start_page", 1))
        self.end_page_var = IntVar(value=self.settings.get_setting("end_page", 0))
        self.skip_pages_var = StringVar(value=self.settings.get_setting("skip_pages", ""))
        self.mode_var = StringVar(value=self.settings.get_setting("_mode", "c"))
        self.dehyphenate_var = BooleanVar(value=self.settings.get_setting("dehyphenate", True))
        self.html_like_var = BooleanVar(value=self.settings.get_setting("html_like", False))
        self.reader_type_var = StringVar(value=self.settings.get_setting("reader_type", "plumber"))

        self.extra_settings_visible = BooleanVar(value=False)
        self.x_tolerance_var = tk.DoubleVar(value=self.settings.get_setting("x_tolerance", 1))
        self.y_tolerance_var = tk.DoubleVar(value=self.settings.get_setting("y_tolerance", 3))
        borders = [None, None, None, None]
        self.left_var = StringVar(value=self.settings.get_setting("borders", borders)[0])
        self.header_var = StringVar(value=self.settings.get_setting("borders", borders)[1])
        self.right_var = StringVar(value=self.settings.get_setting("borders", borders)[2])
        self.footer_var = StringVar(value=self.settings.get_setting("borders", borders)[3])

        # PDF file list
        self.pdf_files = []
        self.current_dir = Path(self.settings.get_setting("last_directory", str(Path(__file__).parent.absolute())))

        # Create main frame with padding
        main_frame = ttk.Frame(root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create scrollable frame
        self.canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows

        # Create the form
        self._create_form()

        # Load PDF files
        self._load_pdf_files()

    def _on_mousewheel(self, event):
        """Handle mousewheel events for scrolling"""
        # Determine the direction of scroll
        if event.num == 5 or event.delta < 0:  # Scroll down
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:  # Scroll up
            self.canvas.yview_scroll(-1, "units")

    def _save_settings(self):
        """Save current settings to file"""
        try:
            # Update settings with current values
            self.settings.update_setting("last_directory", str(self.current_dir))
            self.settings.update_setting("reader_type", self.reader_type_var.get())
            self.settings.update_setting("extract_filetype", self.extract_filetype_var.get())
            self.settings.update_setting("start_page", self.start_page_var.get())
            self.settings.update_setting('end_page', self.end_page_var.get())
            self.settings.update_setting("skip_pages", self.skip_pages_var.get())
            self.settings.update_setting("_mode", self.mode_var.get())
            self.settings.update_setting("dehyphenate", self.dehyphenate_var.get())
            self.settings.update_setting("html_like", self.html_like_var.get())
            self.settings.update_setting("y_tolerance", self.y_tolerance_var.get())
            self.settings.update_setting("x_tolerance", self.x_tolerance_var.get())


            # Border settings
            borders = [
                self.left_var.get() or None,
                self.header_var.get() or None,
                self.right_var.get() or None,
                self.footer_var.get() or None
            ]
            self.settings.update_setting("borders", borders)

            # Save to file
            if self.settings.save_settings():
                self.status_var.set("Settings saved successfully")
            else:
                self.status_var.set("Error saving settings")
        except Exception as e:
            self.status_var.set(f"Error saving settings: {str(e)}")
            messagebox.showerror("Error", f"An error occurred while saving settings: {str(e)}")

    def _create_form(self):
        """Create the input form"""
        # PDF Selection Section
        selection_frame = ttk.LabelFrame(self.scrollable_frame, text="PDF Selection", padding=10)
        selection_frame.pack(fill=tk.X, pady=5)

        # Directory info
        dir_label = ttk.Label(selection_frame, text=f"Current directory: {self.current_dir}")
        dir_label.pack(anchor="w", pady=5)

        # PDF List
        pdf_list_frame = ttk.Frame(selection_frame)
        pdf_list_frame.pack(fill=tk.X, pady=5)

        pdf_list_label = ttk.Label(pdf_list_frame, text="Available PDFs:")
        pdf_list_label.pack(side=tk.LEFT, padx=5)

        self.pdf_combo = ttk.Combobox(pdf_list_frame, textvariable=self.pdf_path_var, state="readonly", width=40)
        self.pdf_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.pdf_combo.bind("<<ComboboxSelected>>", self._on_pdf_selected)

        # Browse button
        browse_button = ttk.Button(selection_frame, text="Browse...", command=self._browse_pdf)
        browse_button.pack(anchor="w", pady=5)

        # Output path
        output_frame = ttk.Frame(selection_frame)
        output_frame.pack(fill=tk.X, pady=5)

        output_label = ttk.Label(output_frame, text="Output file:")
        output_label.pack(side=tk.LEFT, padx=5)

        output_entry = ttk.Entry(output_frame, textvariable=self.output_path_var, width=40)
        output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Extraction filetype
        extract_filetype_frame = ttk.Frame(selection_frame)
        extract_filetype_frame.pack(fill=tk.X, pady=5)

        extract_filetype_label = ttk.Label(extract_filetype_frame, text="Type of output file:")
        extract_filetype_label.pack(side=tk.LEFT, padx=5)

        extract_filetype_json = ttk.Radiobutton(extract_filetype_frame, text="jsonl", variable=self.extract_filetype_var, value="jsonl")
        extract_filetype_json.pack(side=tk.LEFT, padx=5)

        extract_filetype_txt = ttk.Radiobutton(extract_filetype_frame, text="txt", variable=self.extract_filetype_var, value="txt")
        extract_filetype_txt.pack(side=tk.LEFT, padx=5)

        self.extract_filetype_var.trace_add("write", self._on_filetype_change)

        # Page Range Section
        page_frame = ttk.LabelFrame(self.scrollable_frame, text="Page Range", padding=10)
        page_frame.pack(fill=tk.X, pady=5)

        # Start page
        start_frame = ttk.Frame(page_frame)
        start_frame.pack(fill=tk.X, pady=5)

        start_label = ttk.Label(start_frame, text="Start page:")
        start_label.pack(side=tk.LEFT, padx=5)

        start_entry = ttk.Entry(start_frame, textvariable=self.start_page_var, width=10)
        start_entry.pack(side=tk.LEFT, padx=5)

        # End page
        end_frame = ttk.Frame(page_frame)
        end_frame.pack(fill=tk.X, pady=5)

        end_label = ttk.Label(end_frame, text="End page (0 for end):")
        end_label.pack(side=tk.LEFT, padx=5)

        end_entry = ttk.Entry(end_frame, textvariable=self.end_page_var, width=10)
        end_entry.pack(side=tk.LEFT, padx=5)

        # Skip pages
        skip_frame = ttk.Frame(page_frame)
        skip_frame.pack(fill=tk.X, pady=5)

        skip_label = ttk.Label(skip_frame, text="Skip pages (comma separated):")
        skip_label.pack(side=tk.LEFT, padx=5)

        skip_entry = ttk.Entry(skip_frame, textvariable=self.skip_pages_var, width=30)
        skip_entry.pack(side=tk.LEFT, padx=5)

        # Processing Options Section
        options_frame = ttk.LabelFrame(self.scrollable_frame, text="Processing Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        # Reader type
        reader_frame = ttk.Frame(options_frame)
        reader_frame.pack(fill=tk.X, pady=5)

        reader_label = ttk.Label(reader_frame, text="Reader Type:")
        reader_label.pack(side=tk.LEFT, padx=5)

        reader_pymupdf = ttk.Radiobutton(reader_frame, text="PyMuPDF", variable=self.reader_type_var, value="pymupdf")
        reader_pymupdf.pack(side=tk.LEFT, padx=5)

        reader_plumber = ttk.Radiobutton(reader_frame, text="PDFPlumber", variable=self.reader_type_var,
                                         value="plumber")
        reader_plumber.pack(side=tk.LEFT, padx=5)

        # Mode
        mode_frame = ttk.Frame(options_frame)
        mode_frame.pack(fill=tk.X, pady=5)

        mode_label = ttk.Label(mode_frame, text="Processing Mode:")
        mode_label.pack(side=tk.LEFT, padx=5)

        mode_rows = ttk.Radiobutton(mode_frame, text="Rows", variable=self.mode_var, value="r")
        mode_rows.pack(side=tk.LEFT, padx=5)

        mode_columns = ttk.Radiobutton(mode_frame, text="Columns", variable=self.mode_var, value="c")
        mode_columns.pack(side=tk.LEFT, padx=5)

        # Flags
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, pady=5)

        dehy_check = ttk.Checkbutton(format_frame, text="Dehyphenate", variable=self.dehyphenate_var)
        dehy_check.pack(side=tk.LEFT, padx=5)

        html_check = ttk.Checkbutton(format_frame, text="HTML-like formatting", variable=self.html_like_var)
        html_check.pack(side=tk.LEFT, padx=5)

        # Extra Settings Section (collapsible)
        extra_toggle_frame = ttk.Frame(self.scrollable_frame, relief="flat", borderwidth=0)
        extra_toggle_frame.pack(fill=tk.X, pady=5)

        # Toggle button for extra settings
        toggle_button_text = "▼ Show Extra Settings" if not self.extra_settings_visible.get() else "▲ Hide Extra Settings"
        self.toggle_button = ttk.Button(
            extra_toggle_frame,
            text=toggle_button_text,
            command=self._toggle_extra_settings
        )
        self.toggle_button.pack(fill=tk.X)

        # Extra settings container
        self.extra_container = ttk.Frame(self.scrollable_frame, relief="flat", borderwidth=0)
        if self.extra_settings_visible.get():
            self.extra_container.pack(fill=tk.X, pady=5)

        # Border Settings Section
        border_frame = ttk.LabelFrame(self.extra_container, text="Border Settings", padding="10")
        border_frame.pack(fill=tk.X, padx=5, pady=5)
        # Using grid for precise positioning around the page visualization
        border_frame.columnconfigure(0, weight=1)
        border_frame.columnconfigure(1, weight=2)
        border_frame.columnconfigure(2, weight=1)
        border_frame.rowconfigure(0, weight=1)
        border_frame.rowconfigure(1, weight=2)
        border_frame.rowconfigure(2, weight=1)

        # Header (Top)
        header_frame = ttk.Frame(border_frame)
        header_frame.grid(row=0, column=1, sticky="s")
        ttk.Entry(header_frame, textvariable=self.header_var, width=10).pack(pady=(0, 3))
        header_coord_frame = ttk.Frame(header_frame)
        header_coord_frame.pack(pady=(0, 2))
        tk.Label(header_coord_frame, text="(x0, ", font=("Helvetica", 10)).pack(side="left")
        tk.Label(header_coord_frame, text="y0", fg="red", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(header_coord_frame, text=", x1, y1)", font=("Helvetica", 10)).pack(side="left")
        tk.Label(header_frame, text="(More than)", font=("Helvetica", 8, "italic")).pack()

        # Left
        left_frame = ttk.Frame(border_frame)
        left_frame.grid(row=1, column=0, sticky="e")
        ttk.Entry(left_frame, textvariable=self.left_var, width=10).pack(pady=(0, 3))
        left_coord_frame = ttk.Frame(left_frame)
        left_coord_frame.pack(pady=(0, 2))
        tk.Label(left_coord_frame, text="(", font=("Helvetica", 10)).pack(side="left")
        tk.Label(left_coord_frame, text="x0", fg="red", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(left_coord_frame, text=", y0, x1, y1)", font=("Helvetica", 10)).pack(side="left")
        tk.Label(left_frame, text="(More than)", font=("Helvetica", 8, "italic")).pack()

        # Page visualization in center
        page_frame = ttk.Frame(border_frame, borderwidth=2, relief="solid", width=60, height=90)
        page_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        # Using a smaller font for the label to fit in smaller space
        page_label = ttk.Label(page_frame, text="PDF page", font=("Helvetica", 8))
        page_label.place(relx=0.5, rely=0.5, anchor="center")
        # Make the page representation maintain its size
        page_frame.grid_propagate(False)

        # Right
        right_frame = ttk.Frame(border_frame)
        right_frame.grid(row=1, column=2, sticky="w")
        ttk.Entry(right_frame, textvariable=self.right_var, width=10).pack(pady=(0, 3))
        right_coord_frame = ttk.Frame(right_frame)
        right_coord_frame.pack(pady=(0, 2))
        tk.Label(right_coord_frame, text="(x0, y0, ", font=("Helvetica", 10)).pack(side="left")
        tk.Label(right_coord_frame, text="x1", fg="red", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(right_coord_frame, text=", y1)", font=("Helvetica", 10)).pack(side="left")
        tk.Label(right_frame, text="(Less than)", font=("Helvetica", 8, "italic")).pack()

        # Footer (Bottom)
        footer_frame = ttk.Frame(border_frame)
        footer_frame.grid(row=2, column=1, sticky="n")
        ttk.Entry(footer_frame, textvariable=self.footer_var, width=10).pack(pady=(0, 3))
        footer_coord_frame = ttk.Frame(footer_frame)
        footer_coord_frame.pack(pady=(0, 2))
        tk.Label(footer_coord_frame, text="(x0, y0, x1, ", font=("Helvetica", 10)).pack(side="left")
        tk.Label(footer_coord_frame, text="y1", fg="red", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(footer_coord_frame, text=")", font=("Helvetica", 10)).pack(side="left")
        tk.Label(footer_frame, text="(Less than)", font=("Helvetica", 8, "italic")).pack()

        # Threshold Settings
        self.threshold_frame = ttk.LabelFrame(self.extra_container, text="Threshold Settings", padding=10)
        self.threshold_frame.pack(fill=tk.X, pady=5)

        # X tolerance
        x_frame = ttk.Frame(self.threshold_frame)
        x_frame.pack(fill=tk.X, pady=5)

        x_label = ttk.Label(x_frame, text="X tolerance:")
        x_label.pack(side=tk.LEFT, padx=5)

        x_entry = ttk.Entry(x_frame, textvariable=self.x_tolerance_var, width=10)
        x_entry.pack(side=tk.LEFT, padx=5)

        x_help = ttk.Label(x_frame, text="(Higher values combine words spaced further apart)")
        x_help.pack(side=tk.LEFT, padx=5)

        # Y threshold
        y_frame = ttk.Frame(self.threshold_frame)
        y_frame.pack(fill=tk.X, pady=5)

        y_label = ttk.Label(y_frame, text="Y threshold:")
        y_label.pack(side=tk.LEFT, padx=5)

        y_entry = ttk.Entry(y_frame, textvariable=self.y_tolerance_var, width=10)
        y_entry.pack(side=tk.LEFT, padx=5)

        y_help = ttk.Label(y_frame, text="(Higher values combine lines spaced further apart)")
        y_help.pack(side=tk.LEFT, padx=5)

        # Status and action section
        status_frame = ttk.Frame(self.scrollable_frame, padding=10)
        status_frame.pack(fill=tk.X, pady=5)

        # Status label
        self.status_var = StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, font=("", 10, "italic"))
        status_label.pack(anchor="w", pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            status_frame,
            variable=self.progress_var,
            orient="horizontal",
            length=200,
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, pady=5)

        # Execute button
        execute_button = ttk.Button(status_frame, text="Extract PDF", command=self._execute_extraction)
        execute_button.pack(pady=10)

    def _load_pdf_files(self):
        """Load PDF files from the current directory"""
        self.pdf_files = [path.name for path in Path(self.current_dir).glob('*.pdf')]

        # Update combobox
        if self.pdf_files:
            self.pdf_combo['values'] = self.pdf_files
            self.pdf_combo.current(0)
            self._on_pdf_selected(None)  # Trigger the selection event
            self.status_var.set(f"Found {len(self.pdf_files)} PDF files")
        else:
            self.status_var.set("No PDF files found in the current directory")

    def _on_filetype_change(self, *args):
        selected_filetype = self.extract_filetype_var.get()
        output_path = self.output_path_var.get()
        output_path = re.sub(r'\.[^.]*?$'
                             , f'.{selected_filetype}', output_path)
        self.output_path_var.set(output_path)

    def _browse_pdf(self):
        """Open file dialog to browse for a PDF file"""
        filename = filedialog.askopenfilename(
            title="Select a PDF file",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=self.current_dir
        )

        if filename:
            # Update the path variables
            self.current_dir = filename.rsplit('/', 1)[0]
            self._load_pdf_files()
            self.pdf_path_var.set(filename)

            # Update output path
            pdf_name = os.path.basename(filename)
            output_path = re.sub(r'\.pdf'
                                 , '.jsonl', pdf_name)

            self.output_path_var.set(output_path)

            # Reload all files in current directory

            # Update status
            self.status_var.set(f"Selected file: {pdf_name}")

    def _on_pdf_selected(self, event):
        """Handle PDF selection from the dropdown"""
        if self.pdf_combo.get():
            # Update output path
            filetype = self.extract_filetype_var.get()
            pdf_name = self.pdf_combo.get()
            self.pdf_path_var.set(os.path.join(self.current_dir, pdf_name))
            output_path = re.sub(r'\.pdf'
                                 , f'.{filetype}', pdf_name)
            self.output_path_var.set(output_path)

            # Update status
            self.status_var.set(f"Selected file: {pdf_name}")

    def _toggle_extra_settings(self):
        """Toggle visibility of the extra settings panel"""
        if self.extra_settings_visible.get():
            # Hide extra settings
            self.extra_container.pack_forget()
            self.extra_settings_visible.set(False)
            self.toggle_button.config(text="▼ Show Extra Settings")
        else:
            # Show extra settings
            self.extra_container.pack(fill=tk.X, pady=5, after=self.toggle_button.master)
            self.extra_settings_visible.set(True)
            self.toggle_button.config(text="▲ Hide Extra Settings")
            self._toggle_threshold_visibility()

    def _toggle_threshold_visibility(self):
        if self.reader_type_var.get() == "plumber":
            self.threshold_frame.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.threshold_frame.pack_forget()

    def _execute_extraction(self):
        """Execute the PDF extraction based on the form data"""
        try:
            # Validate inputs
            if not self.pdf_path_var.get():
                messagebox.showerror("Error", "Please select a PDF file")
                return

            # Get values from form
            pdf_path = self.pdf_path_var.get()
            if not os.path.isabs(pdf_path):
                pdf_path = os.path.join(self.current_dir, pdf_path)

            output_path = self.output_path_var.get()
            if not os.path.isabs(output_path):
                output_path = os.path.join(self.current_dir, output_path)

            # Create output directory if it doesn't exist
            output_dir = os.path.join(os.path.dirname(output_path), 'output')
            os.makedirs(output_dir, exist_ok=True)

            # Update output path to use the output directory
            output_path = os.path.join(output_dir, os.path.basename(output_path))

            extract_filetype = self.extract_filetype_var.get()

            start_page = self.start_page_var.get()
            end_page = self.end_page_var.get()

            skip_pages_str = self.skip_pages_var.get()
            skip_pages = []
            if skip_pages_str:
                skip_pages = [int(page.strip()) for page in skip_pages_str.split(',') if page.strip()]

            mode = self.mode_var.get()
            dehyphenate = self.dehyphenate_var.get()
            html_like = self.html_like_var.get()


            header = self.header_var.get()
            header = float(header) if header else None
            footer = self.footer_var.get()
            footer = float(footer) if footer else None
            left = self.left_var.get()
            left = float(left) if left else None
            right = self.right_var.get()
            right = float(right) if right else None

            borders = [left, header, right, footer]

            x_tolerance = self.x_tolerance_var.get()
            y_tolerance = self.y_tolerance_var.get()

            self._save_settings()

            # Create parameter dictionary
            params = {
                'pdf_path': pdf_path,
                'output_path': output_path,
                'extract_filetype': extract_filetype,
                'start_page': start_page,
                'end_page': end_page,
                'skip_pages': skip_pages,
                'dehyphenate': dehyphenate,
                'html_like': html_like,
                '_mode': mode,
                'borders': borders,
                'x_tolerance': x_tolerance,
                'y_tolerance': y_tolerance,
                'reader_type': self.reader_type_var.get()
            }

            # Update status
            self.status_var.set("Preparing extraction...")
            self.root.update()

            # Return the parameters
            return params

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            self.status_var.set("Error occurred")
            return None

    def get_parameters(self):
        return self._execute_extraction()

    def run(self):
        self.root.mainloop()

