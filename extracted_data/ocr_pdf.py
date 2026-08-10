import fitz  # pymupdf
import subprocess
import sys
import os
import tempfile

SRC = r"C:\Users\BenTa\OneDrive\Desktop\College Football\Athlon Sports College Football Preview 2026.pdf"
OUT = r"C:\Users\BenTa\AppData\Local\Temp\claude\C--Users-BenTa-OneDrive-Desktop-College-Football\90fc890e-e241-4c6c-a2e5-d4eca96abaec\scratchpad\athlon_2026_ocr.txt"
TESSERACT = r"C:\Users\BenTa\scoop\shims\tesseract.exe"
os.environ["TESSDATA_PREFIX"] = r"C:\Users\BenTa\scoop\apps\tesseract-languages\current"

doc = fitz.open(SRC)
n = doc.page_count
print(f"Total pages: {n}", flush=True)

with tempfile.TemporaryDirectory() as tmpdir:
    with open(OUT, "w", encoding="utf-8") as outf:
        for i in range(n):
            page = doc.load_page(i)
            # Render at ~200 DPI for decent OCR accuracy without huge file sizes
            zoom = 200 / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY)
            img_path = os.path.join(tmpdir, f"page_{i+1}.png")
            pix.save(img_path)

            result = subprocess.run(
                [TESSERACT, img_path, "stdout"],
                capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            text = result.stdout.strip()

            outf.write(f"\n===== PAGE {i+1} =====\n")
            outf.write(text)
            outf.write("\n")
            outf.flush()

            os.remove(img_path)

            if (i + 1) % 10 == 0 or (i + 1) == n:
                print(f"OCR'd {i+1}/{n} pages", flush=True)

print("DONE", flush=True)
