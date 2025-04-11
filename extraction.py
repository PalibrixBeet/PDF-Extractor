from abc import abstractmethod
import json
import re

import fitz
import pdfplumber
from alive_progress import alive_bar


class PDFReader:
    def __init__(self, pdf_path, output_path, start_page=1, end_page=0, skip_pages=None, dehyphenate=True, html_like=False,
                 _mode='c', borders=None, x_tolerance=None, y_tolerance=None):
        if borders is None:
            borders = [None, None, None, None]
        if skip_pages is None:
            skip_pages = []

        self.pdf_path = pdf_path
        self.output_path = output_path

        self.start_page = start_page
        if end_page != 0:
            self.end_page = end_page
        else:
            with fitz.open(self.pdf_path, filetype='pdf') as doc:
                end_page = len(doc)
            self.end_page = end_page
        if self.end_page < self.start_page:
            raise ValueError("end_page cannot be greater than start_page")

        self.skip_pages = [page-1 for page in skip_pages]
        self.total_pages = self.end_page - self.start_page - len(self.skip_pages) + 1

        self.dehyphenate = dehyphenate
        self.html_like = html_like

        self._mode = _mode
        self.borders = borders

        self.x_tolerance = x_tolerance
        self.y_tolerance = y_tolerance

    def filter_by_coordinates(self, block):
        left = self.borders[0]
        header = self.borders[1]
        right = self.borders[2]
        footer = self.borders[3]
        conditions = []

        block_left = block.get('x0') if not 'bbox' in block else block['bbox'][0]
        block_header = block.get('top') if not 'bbox' in block else block['bbox'][1]
        block_right = block.get('x1') if not 'bbox' in block else block['bbox'][2]
        block_footer = block.get('bottom') if not 'bbox' in block else block['bbox'][3]

        if left:
            conditions.append(block_left >= left)
        if header:
            conditions.append(block_header >= header)
        if right:
            conditions.append(block_right <= right)
        if footer:
            conditions.append(block_footer <= footer)
        return conditions

    @staticmethod
    def consolidate_formatting(text):
        tags = ['b', 'i', 'sup']
        tag_pattern = '(' + '|'.join(re.escape(tag) for tag in tags) + ')'
        # debug = '</b></i>    <i><b>    </i></b>    <b><i>     </b></i></sup>    <sup><i><b>  |   <b><i>    </i></b>    <i><b>    </b></i>            <b><i><sup>    </sup></i></b>'

        previous_text = ""
        while text != previous_text:
            previous_text = text

            # 1. <tag>    </tag> -> space
            text = re.sub(r'<' + tag_pattern + r'>(\s*?)</\1>', ' ', text)

            # 2. </tag>   <tag> -> space
            text = re.sub(r'</' + tag_pattern + r'>(\s*?)<\1>', ' ', text)

        return text

    @abstractmethod
    def extract_json(self, app=None):
        pass

    @abstractmethod
    def extract_txt(self, app=None):
        pass

    def write_file(self, app=None, filetype='jsonl'):
        if filetype == 'jsonl':
            lines = self.extract_json(app)
            with open(self.output_path, 'wt', encoding='utf-8') as f:
                for item in lines:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
        else:
            lines = self.extract_txt(app)
            with open(self.output_path, 'wt', encoding='utf-8') as f:
                for item in lines:
                    f.write(item)


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

        with alive_bar(self.total_pages) as bar:
            with pdfplumber.open(self.pdf_path) as pdf:
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
        return lines_by_y

    def store_lines(self, lines, all_lines, line_id, page_num):
        # Second pass: create structured line entries
        for y, line_words in sorted(lines.items()):
            # Skip empty lines
            if not line_words:
                continue

            # Extract text and metadata
            text_parts = []
            for word in line_words:
                text_part = word['text']
                if self.html_like:
                    if word.get('size') < 5:
                        text_part = f'<sup>{text_part}</sup>'
                    if 'Bold' in word.get('fontname', ''):
                        text_part = f'<b>{text_part}</b>'
                    if 'Italic' in word.get('fontname', ''):
                        text_part = f'<i>{text_part}</i>'
                text_parts.append(text_part)
                    # text_parts.append(word['text'])
            # text_parts = [w['text'] for w in line_words]
            fonts = {self.clean_font_name(w.get('fontname', 'unknown')) for w in line_words}
            sizes = {w.get('size', 0) for w in line_words}
            colors = {str(w.get('non_stroking_color', '')) for w in line_words}

            # Calculate accurate bounding box
            x0 = min(w['x0'] for w in line_words)
            y0 = min(w['top'] for w in line_words)
            x1 = max(w['x1'] for w in line_words)
            y1 = max(w['bottom'] for w in line_words)

            all_lines.append({
                'text': self.consolidate_formatting(' '.join(text_parts).replace('\xad', '') + '\n'),
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


class PyMuPDFReader(PDFReader):

    def extract_txt(self, app=None):
        raw_lines = []
        lines = []
        flags = self.get_flags()
        extraction_type = 'html' if self.html_like else 'text'

        try:
            with fitz.open(self.pdf_path, filetype='pdf') as doc:
                print('Processing pages...')

                with alive_bar(self.total_pages) as bar:
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
        # lines = {}
        with fitz.open(self.pdf_path, filetype='pdf') as doc:
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

        print('Processing blocks...')
        all_blocks = []
        with alive_bar(self.total_pages) as bar:
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
                span_text = ''
                font_set = set()
                size_set = set()
                color_set = set()
                for span in line['spans']:
                    font_set.add(span['font'])
                    size_set.add(span['size'])
                    color_set.add(str(span['color']))
                    word = span['text']
                    word_flags = self.flags_decomposer(span['flags'])
                    if self.html_like:
                        if span['size'] < 5:
                            word = '<sup>' + word + '</sup>'
                        if 'Bold' in span['font'] or 'bold' in word_flags:
                            word = '<b>' + word + '</b>'
                        if 'Italic' in span['font'] or 'italic' in word_flags:
                            word = '<i>' + word + '</i>'
                    span_text += word + ' '
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
