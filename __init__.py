# -*- coding: utf-8 -*-
from colorsys import rgb_to_hls, hls_to_rgb
from PIL import Image 
import struct
from cStringIO import StringIO
import os

__author__ = 'Simon Pantzare'
__copyright__ = '2010, %s' % __author__
__license__ = 'MIT'
__version__ = '0.9'

def delta_e(lab1, lab2):
    dist = 0
    for m, n in zip(lab1, lab2):
        dist += (m-n)**2
    return dist

def hex2rgb(c):
    if not len(c) == 6:
        return None
    try:
        c = c.lower()
        split = (c[0:2], c[2:4], c[4:6])
        return tuple([int(x, 16) for x in split])
    except:
        return None

class Color(object):
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b
        self.h, self.l, self.s = rgb_to_hls(r/255.0, g/255.0, b/255.0)
        self.h *= 360
        self.l *= 100
        self.s *= 100

    def h_limits(self, hue_dg):
        """ 0-180 """
        assert 0 <= hue_dg and hue_dg <= 180
        start_h = self.h - hue_dg
        if start_h < 0:
            start_h = 360 + start_h
        end_h = (start_h + 2*hue_dg) % (360 + 1)
        return (start_h, end_h)

    def l_limits(self, l_pc):
        """ 0-50 """
        assert 0 <= l_pc and l_pc <= 50
        minv = max(self.l - l_pc, 0)
        maxv = min(minv + 2*l_pc, 100)
        return (minv, maxv)

    def delta_e_limit(self, hue_dg, l_pc):
        h_min, h_max = self.h_limits(hue_dg)
        l_min, l_max = self.l_limits(l_pc)
        dists = []
        for h, l in [
                (h_min, l_min),
                (h_min, l_max),
                (h_max, l_min),
                (h_max, l_max),
                ]:
            color = Color.from_hls(h, l, self.s)
            dists.append(self.distance_to(color))
        return min(dists)

    def xyz(self):
        """See EasyRGB website."""
        rgb_ = [0,0,0]
        rgb_[0] = self.r / 255.0
        rgb_[1] = self.g / 255.0
        rgb_[2] = self.b / 255.0
        for i, c in enumerate(rgb_):
            if c > 0.04045:
                rgb_[i] = ((c+0.055) / 1.055)**2.4
            else:
                rgb_[i] = c / 12.92
            rgb_[i] *= 100.0

        k1s = [0.4124, 0.3576, 0.1805]
        k2s = [0.2126, 0.7152, 0.0722]
        k3s = [0.0193, 0.1192, 0.9505]
        xyz = [0,0,0]
        for i, k1, k2, k3 in zip(range(3), k1s, k2s, k3s):
            xyz[i] = k1 * rgb_[0] + k2 * rgb_[1] + k3 * rgb_[2] 
        return tuple(xyz)

    def lab(self):
        """See EasyRGB website."""
        xyz = self.xyz()
        xyz_ = [0,0,0]
        xyz_[0] = xyz[0] / 95.047
        xyz_[1] = xyz[1] / 100.0
        xyz_[2] = xyz[2] / 108.883

        for i, c in enumerate(xyz_):
            if c > 0.008856:
                xyz_[i] = xyz_[i]**(1.0/3)
            else:
                xyz_[i] = (7.787 * xyz_[i]) + (16.0 / 116)
        l = (116.0 * xyz_[1]) - 16.0
        a = 500.0 * (xyz_[0] - xyz_[1])
        b = 200.0 * (xyz_[1] - xyz_[2])
        return (l, a, b)

    def distance_to(self, color):
        lab1 = self.lab()
        lab2 = color.lab()
        return delta_e(lab1, lab2)

    def rgb(self):
        return (self.r, self.g, self.b)
    
    @staticmethod
    def from_hex(hex):
        obj = Color(*hex2rgb(hex))
        return obj

    @staticmethod
    def from_hls(h, l, s):
        """
        Ranges 0-360, 0-100, 0-100.
        """
        r,g,b = hls_to_rgb(h/360.0, l/100.0, s/100.0)
        return Color(int(r*255), int(g*255), int(b*255))
        

class RangeImage(object):
    def __init__(
            self, 
            start_rgb, 
            hue_dg,
            lightness_pc, 
            dim=(200,50)
            ):
        """
        lightness_pc 
            Range 0-50%.
            
        hue_dg
            Range 0-180 degrees.
        """
        self.start_color = Color(*start_rgb)
        self.lightness_pc = lightness_pc
        self.hue_dg = hue_dg
        self.width_px = dim[0]
        self.height_px = dim[1]

    def h_vector(self):
        start_h = self.start_color.h_limits(self.hue_dg)[0]
        incr = float(self.hue_dg*2) / self.height_px
        return [(start_h+i*incr)%(360+1) for i in range(0, self.height_px)]

    def l_vector(self):
        minv = self.start_color.l_limits(self.lightness_pc)[0]
        incr = float(self.lightness_pc*2) / self.width_px
        return [min(minv+i*incr,100) for i in range(0, self.width_px)]

    def save(self, outfile):
        x_samples = self.width_px
        y_samples = self.height_px
        h_start = self.start_color.h
        l_start = self.start_color.l
        arr = [[0]*self.width_px for _ in range(self.height_px)]
        hues = self.h_vector()
        ls = self.l_vector()
        sat = self.start_color.s / 100

        max_dist = self.start_color.delta_e_limit(self.hue_dg, self.lightness_pc)
        
        for row_idx, row in enumerate(arr):
            h = hues[row_idx] / 360.0
            for col_idx, px in enumerate(row):
                l = ls[col_idx] / 100.0
                r,g,b = map(lambda x: int(x*255), hls_to_rgb(h, l, sat))
                if max_dist < self.start_color.distance_to(Color(r, g, b)):
                    r, g, b = 255, 255, 255
                arr[row_idx][col_idx] = struct.pack(
                        "BBBB", 
                        r,
                        g,
                        b,
                        255
                        )
        
        buf = StringIO()
        [[buf.write(px) for px in row] for row in arr]
        buf.seek(0)

        im = Image.frombuffer(
                "RGBA", 
                (self.width_px, self.height_px), 
                buf.read(),
                "raw",
                "RGBA",
                0,
                1
                )
        
        with open(outfile, 'w') as f:
            im.save(f, "png")

        return im


if __name__ == '__main__':
    c1 = Color(255, 0, 100)
    for h, l in [
            (0, 0),
            (5, 5),
            (50, 40),
            (180, 50),
            ]:
        print "%.2g" % c1.delta_e_limit(h, l)
        ri = RangeImage(c1.rgb(), h, l)
        ri.save('range_%d_%d.png' % (h, l))
