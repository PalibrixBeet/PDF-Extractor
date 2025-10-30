import re

import unicodedata

import fitz
from alive_progress import alive_bar

from extraction import PDFReader


class PyMuPDFReader(PDFReader):

    def extract_txt(self, app=None):
        raw_lines = []
        lines = []
        flags = self.get_flags()
        extraction_type = 'html' if self.html_like else 'text'

        try:
            with self._open_pdf_doc_pymupdf() as doc:
                if self.print_logs:
                    print('Processing pages...')

                with alive_bar(self.total_pages, disable=not self.print_logs) as bar:
                    for page_num in range(self.start_page - 1, self.end_page):
                        if page_num in self.skip_pages:
                            continue

                        page = doc.load_page(page_num)

                        if self._mode == 'c':
                            width2 = page.rect.width / 2

                            left = page.rect + (0, 0, -width2 + 5, 0)
                            right = page.rect + (width2, 0, 0, 0)

                            if any(self.borders):
                                left = self._apply_borders_to_rect(left)
                                right = self._apply_borders_to_rect(right)

                            raw_lines.append(page.get_text(extraction_type, clip=left, flags=flags))
                            raw_lines.append(page.get_text(extraction_type, clip=right, flags=flags))
                        else:
                            rect = page.rect
                            if any(self.borders):
                                rect = self._apply_borders_to_rect(rect)

                            raw_lines.append(page.get_text(extraction_type, clip=rect, flags=flags))

                        bar()
                        if app:
                            progress = (page_num - self.start_page + 2) / self.total_pages * 100
                            app.root.after(0, lambda p=page_num, prog=progress: (
                                app.status_var.set(f"Processing page #{p + 1}"),
                                app.progress_var.set(prog)
                            ))

            for line in raw_lines:
                lines.extend(line.splitlines(True))

            return lines
        except Exception as e:
            error_msg = f"Error extracting text: {str(e)}"
            print(error_msg)
            if app:
                app.status_var.set(error_msg)
            return []

    def extract_json(self, app=None):
        with self._open_pdf_doc_pymupdf() as doc:
            blocks = self.get_blocks(doc, app)
            lines = self.get_lines_by_blocks(blocks)
        return lines

    def flags_decomposer(self, flags):
        """Make font flags human readable."""
        l = []
        # Text positioning
        if flags & 2 ** 0:
            l.append("superscript")
        if flags & 2 ** 5:
            l.append("subscript")

        # Style attributes
        if flags & 2 ** 1:
            l.append("italic")
        elif flags & 2 ** 7:
            l.append("synthetic-italic")  # Fake italic

        if flags & 2 ** 4:
            l.append("bold")
        elif flags & 2 ** 6:
            l.append("synthetic-bold")  # Fake bold

        # Font characteristics
        if flags & 2 ** 2:
            l.append("serifed")
        else:
            l.append("sans")

        if flags & 2 ** 3:
            l.append("monospaced")
        else:
            l.append("proportional")

        if flags & 2 ** 8:
            l.append("symbolic")

        if flags & 2 ** 9:
            l.append("invisible")

        if flags & 2 ** 10:
            l.append("truetype")

        return ", ".join(l)

    def get_flags(self):
        flags = 0
        # flags = flags | fitz.TEXT_PRESERVE_SPANS
        if self.dehyphenate:
            flags |= fitz.TEXT_DEHYPHENATE
        return flags

    def get_blocks(self, doc, app=None):
        flags = self.get_flags()

        if self.print_logs:
            print('Processing blocks...')
        all_blocks = []
        with alive_bar(self.total_pages, disable=not self.print_logs) as bar:
            for page_num in range(self.start_page - 1, self.end_page):
                if page_num in self.skip_pages:
                    continue
                page = doc.load_page(page_num)
                if self._mode == 'c':
                    width2 = page.rect.width / 2
                    left = page.rect + (0, 0, -width2 + 5, 0)  # the left half page
                    right = page.rect + (width2, 0, 0, 0)  # the right half page
                    lblocks = page.get_text("dict", clip=left, sort=True, flags=flags)["blocks"]
                    rblocks = page.get_text("dict", clip=right, sort=True, flags=flags)["blocks"]
                    blocks = lblocks + rblocks
                else:
                    blocks = page.get_text("dict", sort=True, flags=flags)["blocks"]

                blocks = self._preprocess_blocks(blocks)

                for block in blocks:
                    if block['type'] != 0:
                        continue
                    if not all(self.filter_by_coordinates(block)):
                        print('Skipped: ', ' '.join([span['text'] for line in block['lines'] for span in line['spans']]))
                        continue
                    all_blocks.append(block | {'page': page_num})
                bar()
                if app:
                    progress = (page_num - self.start_page + 2) / self.total_pages * 100
                    app.root.after(0, lambda p=page_num, prog=progress: (
                        app.status_var.set(f"Processing blocks on page #{p}"),
                        app.progress_var.set(prog)
                    ))
        return all_blocks

    def get_lines_by_blocks(self, blocks):
        lines = []
        for i, block in enumerate(blocks):
            for line in block['lines']:
                line_parts = []
                font_set = set()
                size_set = set()
                color_set = set()

                for span in line['spans']:
                    font_set.add(span['font'])
                    size_set.add(span['size'])
                    color_set.add(str(span['color']))

                    word = span['text']

                    # 1. Determine if the current span is just a combining character.
                    # 'Mn' = Non-Spacing Mark, 'Mc' = Spacing Combining Mark
                    is_combining_mark = False
                    if word:  # Ensure the string is not empty
                        is_combining_mark = all(unicodedata.category(c) in ('Mn', 'Mc') for c in word)

                    # 2. Apply HTML-like formatting to the word
                    word_flags = self.flags_decomposer(span['flags'])
                    if self.html_like:
                        if span['size'] < self.sup_size:
                            word = f'<sup>{word}</sup>'
                        if any(font in span['font'] for font in self.bold_fonts) or 'bold' in word_flags:
                            word = f'<b>{word}</b>'
                        if any(font in span['font'] for font in self.italic_fonts) or 'italic' in word_flags:
                            word = f'<i>{word}</i>'

                    # 3. Append intelligently
                    if is_combining_mark and line_parts:
                        # If it's a combining mark, attach it to the previous part
                        line_parts[-1] += word
                    else:
                        # Otherwise, add it as a new part (will be joined by spaces later)
                        line_parts.append(word)

                # Join the parts with spaces
                span_text = ' '.join(line_parts)
                span_text = self.consolidate_formatting(span_text)
                lines.append({'text': span_text, 'font': list(font_set), 'size': list(size_set), 'color': list(color_set),
                              'bbox': block['bbox'], 'page': block['page'], '_id': i})
        return lines

    def _apply_borders_to_rect(self, rect):
        """
        Apply border constraints to a rectangle.

        Args:
            rect: A fitz.Rect object to modify

        Returns:
            Modified fitz.Rect object or None if rect would be invalid
        """
        left, header, right, footer = self.borders

        # Create a copy of the rect to modify
        modified_rect = fitz.Rect(rect)

        # Apply constraints
        if left is not None and left > modified_rect.x0:
            modified_rect.x0 = left
        if header is not None and header > modified_rect.y0:
            modified_rect.y0 = header
        if right is not None and right < modified_rect.x1:
            modified_rect.x1 = right
        if footer is not None and footer < modified_rect.y1:
            modified_rect.y1 = footer

        # Check if rectangle is still valid (has positive area)
        if modified_rect.x1 <= modified_rect.x0 or modified_rect.y1 <= modified_rect.y0:
            return None

        return modified_rect

    def _preprocess_blocks(self, blocks):

        # Merge when separate words of same line are in separate lines
        for block in blocks:
            if block["type"] == 0 and self.y_tolerance:  # text block
                merged_lines = []
                current_line = None

                for line in block["lines"]:
                    if current_line is None:
                        current_line = line
                    else:
                        # Check if lines should be merged based on y-coordinate proximity
                        y_tolerance = self.y_tolerance
                        if abs(current_line["bbox"][1] - line["bbox"][1]) <= y_tolerance:
                            # Merge spans from this line into current_line
                            current_line["spans"].extend(line["spans"])
                            # Update bbox
                            current_line["bbox"] = (
                                min(current_line["bbox"][0], line["bbox"][0]),
                                min(current_line["bbox"][1], line["bbox"][1]),
                                max(current_line["bbox"][2], line["bbox"][2]),
                                max(current_line["bbox"][3], line["bbox"][3])
                            )
                        else:
                            merged_lines.append(current_line)
                            current_line = line

                if current_line:
                    merged_lines.append(current_line)

                block["lines"] = merged_lines

        # Merge spans with no gap between them, like "O ’ Connor" -> "O’Connor"
        for block in blocks:
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    if len(line["spans"]) <= 1:
                        continue

                    merged_spans = []
                    current_span = None

                    for span in line["spans"]:
                        if current_span is None:
                            current_span = span.copy()
                        else:
                            # Check if spans should be merged:
                            # 1. Same font size
                            # 2. Same font name (also, make fonts like 'AdvOT863180fb+20' and 'AdvOT863180fb' the same)
                            # 3. No space between them (check x-coordinates)
                            same_size = abs(current_span["size"] - span["size"]) < 0.01
                            if '+' in current_span["font"] or '+' in span["font"]:
                                same_font = re.sub(r'\+\d+|', '', current_span["font"]) == re.sub(r'\+\d+', '', span["font"])
                            else:
                                same_font = current_span["font"] == span["font"]

                            # Check if there's a gap between spans
                            # current_span ends at bbox[2], span starts at bbox[0]
                            x_gap = span["bbox"][0] - current_span["bbox"][2]
                            # Allow small tolerance for rounding errors
                            no_gap = x_gap < 1.0  # adjust tolerance as needed

                            if same_size and same_font and no_gap:
                                # Merge spans
                                current_span["text"] += span["text"]
                                # Update bbox to encompass both spans
                                current_span["bbox"] = (
                                    current_span["bbox"][0],
                                    min(current_span["bbox"][1], span["bbox"][1]),
                                    span["bbox"][2],
                                    max(current_span["bbox"][3], span["bbox"][3])
                                )
                                # Update origin to the rightmost position
                                current_span["origin"] = span["origin"]
                            else:
                                # Can't merge, save current and start new
                                merged_spans.append(current_span)
                                current_span = span.copy()

                    if current_span:
                        merged_spans.append(current_span)

                    line["spans"] = merged_spans

        return blocks
