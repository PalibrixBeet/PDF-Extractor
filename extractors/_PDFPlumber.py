import re

import unicodedata
from alive_progress import alive_bar

from PDFExtractor.extraction import PDFReader


class PDFPlumberReader(PDFReader):

    def extract_txt(self, app=None):
        raw_lines = self.extract_json(app)
        lines = []
        for line in raw_lines:
            lines.append(line['text'])
        return lines

    def extract_json(self, app=None):
        all_lines = []
        line_id = 0

        with alive_bar(self.total_pages, disable=not self.print_logs) as bar:
            with self._open_pdf_doc_pdfplumber() as pdf:
                for page_num in range(self.start_page - 1, self.end_page):
                    if page_num in self.skip_pages:
                        continue

                    page = pdf.pages[page_num]
                    width = page.width
                    height = page.height

                    if self._mode == 'c':
                        for half_idx, crop_box in enumerate([
                            (0, 0, width / 2 + 5, height),  # left half
                            (width / 2, 0, width, height)  # right half
                        ]):
                            page_content = page.crop(crop_box)

                            lines_by_y = self.group_lines(page_content)
                            all_lines, line_id, page_num = self.store_lines(lines_by_y, all_lines, line_id, page_num)
                    else:
                        lines_by_y = self.group_lines(page)
                        all_lines, line_id, page_num = self.store_lines(lines_by_y, all_lines, line_id, page_num)


                    bar()
                    if app:
                        progress = (page_num - self.start_page + 2) / self.total_pages * 100
                        app.root.after(0, lambda p=page_num, prog=progress: (
                            app.status_var.set(f"Processing page #{p}"),
                            app.progress_var.set(prog)
                        ))
        if self.dehyphenate:
            all_lines = self.perform_dehyphenate(all_lines)

        return all_lines

    def group_lines(self, page_content):
        words = page_content.extract_words(
            keep_blank_chars=True,
            x_tolerance=self.x_tolerance,
            # use_text_flow=True,
            extra_attrs=['fontname', 'size', 'stroking_color', 'non_stroking_color']
        )

        content_words = [w for w in words if all(self.filter_by_coordinates(w))]
        skipped_words = [w for w in words if not all(self.filter_by_coordinates(w))]
        if skipped_words:
            print('Skipped: ', ' '.join([line['text'] for line in skipped_words]))

        if not content_words:
            return {}

        y_tolerance = self.y_tolerance
        lines_by_y = {}

        # First pass: group words by y-position
        for word in content_words:
            # Find the closest y-position within threshold
            y_key = None
            for y in lines_by_y.keys():
                if abs(word['top'] - y) <= y_tolerance:
                    y_key = y
                    break

            if y_key is None:
                y_key = word['top']
                lines_by_y[y_key] = []

            lines_by_y[y_key].append(word)

        lines = [line[1] for line in sorted(lines_by_y.items())]

        # Group spans by X now
        processed_lines = []

        for line in lines:
            # A line is a list of word dictionaries (which we'll treat as spans)
            if len(line) <= 1:
                processed_lines.append(line)
                continue

            merged_spans = []
            # Start with the first word/span in the line
            current_span = line[0].copy()

            # Iterate through the rest of the spans in the line
            for i in range(1, len(line)):
                span = line[i]

                # Condition 1: Same font size (with a small tolerance)
                same_size = abs(current_span["size"] - span["size"]) < 0.01

                # Condition 2: # Same font name (also, making fonts like 'AdvOT863180fb+20' and 'AdvOT863180fb' the same and remove 'NJHPPA+' from 'NJHPPA+AdvOT863180fb')
                if '+' in current_span["fontname"] or '+' in span["fontname"]:
                    same_font = re.sub(r'^[A-Z]+\+|\+\d+', '', current_span["fontname"]) == re.sub(r'^[A-Z]+\+|\+\d+', '', span["fontname"])
                else:
                    same_font = current_span["fontname"] == span["fontname"]

                # Condition 3: No significant horizontal gap between spans.
                # current_span ends at "x1", the next span starts at "x0".
                x_gap = span["x0"] - current_span["x1"]
                no_gap = x_gap < 1.0  # Tolerance can be adjusted

                if same_size and same_font and no_gap:
                    current_span["text"] += span["text"]

                    current_span["x1"] = span["x1"]
                    current_span["top"] = min(current_span["top"], span["top"])
                    current_span["bottom"] = max(current_span["bottom"], span["bottom"])
                else:
                    merged_spans.append(current_span)
                    current_span = span.copy()

            if current_span:
                merged_spans.append(current_span)

            processed_lines.append(merged_spans)

        return processed_lines

    def store_lines(self, lines, all_lines, line_id, page_num):
        for line_words in lines:
            if not line_words:
                continue

            text_parts = []
            fonts = set()
            sizes = set()
            colors = set()

            for word_info in line_words:
                fonts.add(self.clean_font_name(word_info.get('fontname', 'unknown')))
                sizes.add(word_info.get('size', 0))
                colors.add(str(word_info.get('non_stroking_color', '')))

                text_part = word_info['text']

                # 1. Check if this "word" is just a combining accent
                is_combining_mark = False
                if text_part:
                    is_combining_mark = all(unicodedata.category(c) in ('Mn', 'Mc') for c in text_part)

                # 2. Apply HTML formatting
                if self.html_like:
                    if word_info.get('size') < self.sup_size:
                        text_part = f'<sup>{text_part}</sup>'
                    if any(font in word_info.get('fontname', '') for font in self.bold_fonts):
                        text_part = f'<b>{text_part}</b>'
                    if any(font in word_info.get('fontname', '') for font in self.italic_fonts):
                        text_part = f'<i>{text_part}</i>'

                # 3. Append intelligently
                if is_combining_mark and text_parts:
                    # Attach to the previous part without a space
                    text_parts[-1] += text_part
                else:
                    # Add as a new part
                    text_parts.append(text_part)

            fonts = {self.clean_font_name(w.get('fontname', 'unknown')) for w in line_words}
            sizes = {w.get('size', 0) for w in line_words}
            colors = {str(w.get('non_stroking_color', '')) for w in line_words}

            # Join the processed parts with a space
            final_text = ' '.join(text_parts).replace('\xad', '')
            final_text = self.consolidate_formatting(final_text)

            # Calculate accurate bounding box
            x0 = min(w['x0'] for w in line_words)
            y0 = min(w['top'] for w in line_words)
            x1 = max(w['x1'] for w in line_words)
            y1 = max(w['bottom'] for w in line_words)

            all_lines.append({
                'text': final_text,
                'font': list(fonts),
                'size': list(sizes),
                'color': list(colors),
                'bbox': [x0, y0, x1, y1],
                'page': page_num,
                '_id': line_id
            })
            line_id += 1
        return all_lines, line_id, page_num

    @staticmethod
    def clean_font_name(font_name: str):
        if '+' in font_name:
            return font_name.partition('+')[2]
        return font_name

    def perform_dehyphenate(self, all_lines):
        if not all_lines:
            return []

        results = []
        i = 0

        while i < len(all_lines):
            current_line = dict(all_lines[i])  # Make a copy to avoid modifying original

            # Process consecutive hyphens with a forward-looking approach
            while current_line['text'].endswith('-\n') and i + 1 < len(all_lines):
                next_line = all_lines[i + 1]

                # Check if lines are in the same context or at page boundary
                same_context = (current_line['page'] == next_line['page'])
                page_boundary = (current_line['page'] + 1 == next_line['page'])

                if not (same_context or page_boundary):
                    break

                # Get parts for merging
                dehyphenated_text = re.sub('-\n', '', current_line['text'] + next_line['text'], count=1)
                current_line['text'] = dehyphenated_text

                # Expand bounding box to include next line
                current_line['bbox'] = [
                    min(current_line['bbox'][0], next_line['bbox'][0]),
                    current_line['bbox'][1],  # Keep top of first line
                    max(current_line['bbox'][2], next_line['bbox'][2]),
                    next_line['bbox'][3]  # Use bottom of last line
                ]

                # Update metadata sets (fonts, sizes, colors)
                for attr in ['font', 'size', 'color']:
                    if attr in current_line and attr in next_line:
                        current_set = set(current_line[attr])
                        next_set = set(next_line[attr])

                        current_line[attr] = list(current_set.union(next_set))

                # Move to next line for next iteration
                i += 1
                if i + 1 >= len(all_lines):
                    break

            # Add the processed line to results
            results.append(current_line)
            i += 1

        return results
