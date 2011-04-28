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
    
    pix = QPixmap(width, height)
    pix.fill(QColor('black'))

    p = QPainter()
    p.begin(pix)
    p.setFont(font)
    p.setPen(QColor('white'))
    p.setBackgroundColor(QColor('black'))
    p.drawText(0, 0, width, height, 0, text)
    p.end()

    if not pix.save(path, "PNG"):
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

