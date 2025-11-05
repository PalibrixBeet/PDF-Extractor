from abc import abstractmethod
import json
import re

import fitz
import pdfplumber


class PDFReader:
    def __init__(self, pdf_path, output_path, start_page=1, end_page=0, skip_pages=None, dehyphenate=False, html_like=True,
                 sup_size=6, _mode='c', borders=None, x_tolerance=1.5, y_tolerance=3, is_stream=False, print_logs=True):
        if borders is None:
            borders = [None, None, None, None]
        if skip_pages is None:
            skip_pages = []

        self.is_stream = is_stream
        self.print_logs = print_logs

        self.bold_fonts = ['Bold', '.B', '.BI']
        self.italic_fonts = ['Italic', '.I', '.BI']
        self.sup_size = sup_size

        self.pdf_path = pdf_path
        self.output_path = output_path

        self.start_page = start_page
        if end_page != 0:
            self.end_page = end_page
        else:
            with self._open_pdf_doc_pymupdf() as doc:
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

    def _open_pdf_doc_pymupdf(self):
        if self.is_stream:
            return fitz.open(stream=self.pdf_path, filetype='pdf')
        return fitz.open(self.pdf_path, filetype='pdf')

    def _open_pdf_doc_pdfplumber(self):
        if self.is_stream:
            import io
            return pdfplumber.open(io.BytesIO(self.pdf_path))
        return pdfplumber.open(self.pdf_path)

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

            # 3. Some extra specific patterns like </i> ’ <i>
            text = re.sub(r'</' + tag_pattern + r'>\s*(’)\s*<\1>', r'\2', text)

        # 4 Removes one space before <tag> and one after </tag> after joining text, BUT ONLY ONCE
        text = re.sub(rf'\s(<{tag_pattern}>)|(</{tag_pattern}>)\s', r'\1\3', text)

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
                    f.write(item + '\n')
