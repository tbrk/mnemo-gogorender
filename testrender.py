#!/usr/bin/python
# encoding: utf-8

from PyQt4.QtCore import *
from PyQt4.QtGui import * # For QApplication
import sys, traceback

def drawtext(width, height, font, color, text, path, transparent=True):
    img = QImage(width, height, QImage.Format_ARGB32)

    if transparent:
        img.fill(qRgba(0,0,0,0))
    else:
        img.fill(qRgba(255,255,255,255))

    p = QPainter()
    p.begin(img)
    p.setFont(font)
    p.setPen(QColor(color))
    p.drawText(0, 0, width, height, 0, text)
    p.end()

    if img.save(path, "PNG"):
        return path
    else:
        return None

def render_word(word, font, fontsize):
    path = 'test-%s-%s.png' % (font.replace(' ', '_'),
                               word.encode('punycode').replace(' ', '_'))

    text = QString(word)

    font = QFont(font, fontsize, QFont.Normal, False)
    fm = QFontMetrics(font)
    width = fm.width(text) + (fm.charWidth('M', 0) / 2)
    height = fm.height()

    drawtext(width, height, font, 'blue', word, path, True)

# - - - test - - -

app = QApplication(sys.argv)

testfonts = ['Helvetica', 'DejaVu Sans']
testtext = [u'Test', u'bɔ̃ʒuʀ', u'ελληνική γλώσσα']

for font in testfonts:
    for text in testtext:
        try:
            render_word(text, font, 48)
        except:
            print traceback.format_exc()
            print "failed to render '%s' with %s" % (text, font)
            sys.exit(1)

