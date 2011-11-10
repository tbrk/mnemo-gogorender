# encoding: utf-8

from qt import *
import sys, traceback
from mnemosyne.core import *
import re

class TestRender(Plugin):
    version = "1.0.0"
    destination = "/Users/<yourusername>"

    def render_word(self, word, font, fontsize):
        path = '%s/test-%s-%s.png' % (self.destination,
                               font.replace(' ', '_'),
                               word.encode('punycode').replace(' ', '_'))
    
        text = QString(word)
    
        font = QFont(font, fontsize, QFont.Normal, False)
        fm = QFontMetrics(font)
        width = fm.width(text) + (fm.charWidth('M', 0) / 2)
        height = fm.height()
        
        pix = QPixmap(width, height)
        pix.fill(QColor('white'))
    
        p = QPainter()
        p.begin(pix)
        p.setFont(font)
        p.setPen(QColor('black'))
        p.drawText(0, 0, width, height, 0, text)
        p.end()
    
        if not pix.save(path, "PNG"):
            print "could not save to %s" % path

    def description(self):
        return ("Description")

    def load(self):
        testfonts = ['Helvetica', 'DejaVu Sans']
        testtext = [u'Test', u'bɔ̃ʒuʀ', u'ελληνική γλώσσα']

        for font in testfonts:
            for text in testtext:
                self.render_word(text, font, 48)

    def unload(self):
        pass

p = TestRender()
p.load()

