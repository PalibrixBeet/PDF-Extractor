import logging
import sys
import threading
import tkinter as tk
from tkinter import ttk

from extraction import PDFPlumberReader, PyMuPDFReader
from ui import get_user_data, get_user_data_debug, PDFReaderGUI
from settings import Settings


pdflogs = ([logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith('pdfminer')] +
           [logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith('pdfplumber')])
for ll in pdflogs:
    ll.setLevel(logging.ERROR)


def main():
    root = tk.Tk()
    app = PDFReaderGUI(root)

    params = None

    def on_extract():
        params = app._execute_extraction()
        if params is None:
            print("Operation canceled by user")
            return
        reader_type = params.pop('reader_type')
        extract_filetype = params.pop('extract_filetype')
        if reader_type == 'pymupdf':
            reader = PyMuPDFReader(**params)
        else:
            reader = PDFPlumberReader(**params)

        def run_extraction():
            try:
                reader.write_file(app, extract_filetype)
                # Use after() to update UI from thread safely
                app.root.after(0, lambda: app.status_var.set(
                    f"Extraction complete.\nOutput saved to {reader.output_path}"))
                app.root.after(0, lambda: print(f"Extraction complete. \nOutput saved to {reader.output_path}"))
            except Exception as e:
                app.root.after(0, lambda: app.status_var.set(f"Error: {str(e)}"))
                app.root.after(0, lambda: print(f"Error: {str(e)}"))

        # Start the thread
        extraction_thread = threading.Thread(target=run_extraction)
        extraction_thread.daemon = True  # Thread will exit when main program exits
        extraction_thread.start()

    def on_cancel():
        root.quit()

    for widget in app.scrollable_frame.winfo_children():
        if isinstance(widget, ttk.Frame):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and child['text'] == "Extract PDF":
                    child['command'] = on_extract

    # Add a cancel button
    cancel_button = ttk.Button(app.scrollable_frame, text="Cancel", command=on_cancel)
    cancel_button.pack(pady=5)

    root.mainloop()
    try:
        root.destroy()
    except tk.TclError:
        pass


if __name__ == '__main__':
    # if len(sys.argv) > 1 and sys.argv[1] in ['-g', '--gui']:
    main()
    # else:
    #     main()