"""usage: corners.py src out.jpg radius x,y x,y ...   zoomed gridded views around source points"""
import sys
import sheet
a = sys.argv[1:]
sheet.corners(a[0], a[1], [tuple(int(v) for v in p.split(",")) for p in a[3:]], r=int(a[2]))
