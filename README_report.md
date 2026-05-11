# Report Generation

This directory contains the IEEE-style report generator for the ANPR project.

## Quick Start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the report generator:

```bash
python generate_report.py
```

3. Output files:
   - `report.docx` - Professional IEEE-style Word report
   - `report_assets/` - Generated figures (dataset distribution, training curves, pipeline diagram)

## Features

- **Automated figure generation** using matplotlib and seaborn
- **Professional formatting** with IEEE conference style
- **Real data integration** - scans workspace for actual plate samples
- **Simulated placeholders** when real data isn't available
- **Clean, editable document** in Word format

## Report Sections

1. Title Page with author information
2. Abstract and Keywords
3. Introduction
4. Objectives
5. Related Work (with comparison table)
6. Theory & Method
7. Implementation Details
8. Experiments & Results (with figures)
9. Conclusion & Future Work
10. Acknowledgments
11. References

## Requirements

- Python 3.10+
- python-docx 1.1.0+
- matplotlib 3.8.0+
- seaborn 0.13.0+
- numpy 1.26.0+
- pillow 10.1.0+

See `requirements.txt` for complete list.

## Notes

- All generated figures are saved to `report_assets/` at 300 DPI for high quality
- The document uses Times New Roman font throughout per IEEE standards
- Real detection samples are auto-collected from `backend/debug_plates/` if available
