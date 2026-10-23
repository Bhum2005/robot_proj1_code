# ผังการทำงาน

`flowcharts.pdf` — 11 ผัง: server · จอย · ขับเคลื่อน · เก็บขยะ · กล้อง · แขนกล้อง · ภาพสดบนเว็บ ·
ถ่ายรูป→AI→บันทึก→hub · AI อ่านเลข · เว็บหอพัก (เจ้าของหอ + ลูกหอ) · ภาพรวม

วาดใหม่: ต้องมี Graphviz (`dot`) ฟอนต์ Loma (`fonts-tlwg-loma`) และ `pip install pypdf`

```bash
cd docs/flowcharts && python3 gen.py      # ได้ c01..c11 + flowcharts-3.pdf
```
