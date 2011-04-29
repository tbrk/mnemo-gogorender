#!/usr/bin/python
# encoding: utf-8

from qt import *
import sys, traceback

def render_word(word, font, fontsize):
    path = 'test-%s-%s.png' % (font.replace(' ', '_'),
			       word.encode('punycode').replace(' ', '_'))

    text = QString(word)

    font = QFont(font, fontsize, QFont.Normal, False)
    fm = QFontMetrics(font)
    width = fm.width(text) + (fm.charWidth('M', 0) / 2)
    height = fm.height()

    # Almost works, but strange bug in output...
    #img = QImage(width, height, 32)
    #img.setAlphaBuffer(1)
    #img.fill(qRgba(0, 0, 0, 0))
    #pix = QPixmap(img)
    #if pix.hasAlpha(): print "has alpha!"

    # Alternative: create a pixmap with a colour table
    #		   draw as pure red, then iterate through the colour table
    #		   copying red element to alpha and setting rgb to desired
    #		   colour
    # 
    pix = QPixmap(width, height)
    pix.fill(QColor('black'))

    p = QPainter()
    p.begin(pix)
    p.setFont(font)
    p.setPen(QColor(255,0,0)) # all red
    p.setBackgroundColor(QColor('black'))
    p.drawText(0, 0, width, height, 0, text)
    p.end()

    img = pix.convertToImage()
    img.setAlphaBuffer(1)

    c = QColor('red')
    r = qRed(c.rgb())
    b = qBlue(c.rgb())
    g = qGreen(c.rgb())

    for x in range(0, img.width()):
	for y in range(0, img.height()):
	    pix = img.pixel(x, y)
	    img.setPixel(x, y, qRgba(r, b, g, qRed(pix)))

    if not img.save(path, "PNG"):
	print "could not save to %s" % path

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

