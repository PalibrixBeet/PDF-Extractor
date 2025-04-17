# PDF Extractor
___

## 📝 Table of Contents
1. [Installation](#installation)
2. [Test PDFs](#test-pdfs)
3. [Instructions](#instructions)
   * [PyMuPDF](#pymupdf)
   * [PDFPlumber](#pdfplumber)
4. [Summary](#summary)

## Installation
1. Clone GitHub project: 
```git clone https://github.com/PalibrixBeet/PDF-Extractor```
2. Install requirements*:
```pip install -r requirements.txt```

#### *Note: you must use at least Python 3.11 to install all requirements.

## Test PDFs:
1. PDF_Test_borders_styles - basic pdf with some border text and different styles
2. PDF_Test_tolerance.pdf - Example of a PDF page that cannot be processed by PyMuPDF - skipped lines are shown as "­" (use editor mode to see hidden symbol)


## Instructions
- #### Important info - dehyphenation is not smart. It combines two lines, if the first one end with "-"
- #### Important info - those libraries uses slightly different coordinates (off by 10 or so) for skipping text

### PyMuPDF

Best for most use cases. Sometimes might skip lines. Most things are automated.
Change to PDFPlumber if you noticed at least one skipped line, but 95% of PDFs are structured well enough to use this 



### PDFPlumber

The main think here is to manage thresholds. What are those?
<details>
<summary>

___
#### X Tolerance - how far away separate words are in one line. Base recommended value - 1.5;
___
</summary>
Adds a space between characters, when distance between them more that this value.

For example, if you would set it to any negative value - it would separate all characters as "C O M P A R A C I Ó N   C L Í N I C A".
Useful when words are to close to each other in one line to separate them
</details>

<details>
<summary>

___ 
#### Y Tolerance - how far away each line from one another; Base recommended value - 3
___
</summary>

To separate lines, that are too close. 
* If values are too high - might skip lines
* If values are too low - might think that some words are not the same line, but separate. Specifically when there are some small characters (affiliation keys, for example) 

Useful when lines are to close to each other. PyMuPDF will return weird symbols or skip lines in this case.
</details>

## Summary

|            | Plain text                                                                                                                         | Text + HTML                                                                                                                                                                                            | JSONL                                                                                                                                   | JSONL + HTML                                                                                                               | Speed                                                       |
|:-----------|:-----------------------------------------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------|
| PyMuPDF    | + The most accurate<br/>+ Can read lines in any direction<br/> + Will skip hidden text automatically <br/>- Can't remove borders** | + DOM-structured<br/> + Includes fonts and sizes as attributes <br/> - Sometimes rows are overlapping if viewed as HTML. View the structure in browser and check outputs<br/> - Can't remove borders** | - May replace some lines with unknown symbols <br/> - No manual thresholds                                                              | + Can format \<b>, \<i>, \<sup>* <br/> + Can process extra hidden fonts<br/> - May replace some lines with unknown symbols | Fastest in any mode; <br/> Up to 300 pages per second       |
| PDFPlumber | + Same as JSON extraction, just without styles and as plain lines <br/> - Less accurate<br/> - Can't read rotated text accurately  | + Can format \<b>, \<i>, \<sup>* <br/> + Same as JSON extraction <br/> - Can't read rotated text accurately                                                                                            | + May be more accurate in some scenarios, but requires manually specifying x and y thresholds<br/> - Can't read rotated text accurately | + Can format \<b>, \<i>, \<sup>* <br/> - Can't process extra hidden fonts<br/> - Can't read rotated text accurately        | Default: up to 6 pages, per second; <br/> Debug: 1-2 pages, |

\* \<sup> style is hardcoded to all fonts of 5 and below. Test feature, waiting for a feedback

\** Actually, can, but won't output removed lines. Also - it uses different coordinates, fill free to experiment