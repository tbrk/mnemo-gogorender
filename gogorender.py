# encoding: utf-8
##############################################################################
#
# gogorender.py 2.x
# Timothy Bourke <tim@tbrk.org>
#
# Plugin for rendering segments of text as image files.
#
# The main reason for this plugin is to work around the limitations of
# displaying fonts under J2ME on certain mobile phones. Characters can
# instead be rendered on a PC where more fonts and libraries are available.
#
# NB: On phones where security prompts cannot be disabled, each image
#     will generate a confirmation prompt. This can quickly become annoying.
#
##############################################################################

from PyQt4 import QtCore
from PyQt4 import QtGui
from PyQt4.QtGui import QTextDocument, QTextCursor
from PyQt4.QtCore import QRegExp

from mnemosyne.libmnemosyne.hook import Hook
from mnemosyne.libmnemosyne.filter import Filter
from mnemosyne.libmnemosyne.plugin import Plugin
from mnemosyne.libmnemosyne.ui_components.configuration_widget import \
   ConfigurationWidget

import sys
import re
from copy import copy
import os, os.path
import shutil
import math

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

def tr(msg):
    return QtCore.QCoreApplication.translate("Mnemogogo", msg)

name = "Gogorender"
version = "2.0.1"

render_chains = ["mnemogogo"]

# \xfffc is the "Object Replacement Character" (used for images)
# \x2028 is the "Line Separator"
# \x2029 is the "Paragraph Separator"
not_word = u'[\s\u2028\u2029\ufffc]'
not_line = u'[\r\n\u2028\u2029\ufffc]'

default_config = {
    'transparent'      : True,
    'render_char'      : u'[\u0100-\uff00]',
    'not_render_char'  : u'[—≠–œ‘’“”…€]',
    'render_line_tags' : u'',
    'max_line_width'   : 240,
    'font_scaling'     : 1.0,

    'default_render'  : False,
}

body_match_re = re.compile(r'^.*<body[^>]*>\n*(?P<body>.*)\n*</body>.*$',
                           re.DOTALL)

def translate(text):
    return text

class GogorenderConfig(Hook):
    used_for = "configuration_defaults"

    def run(self):
        self.config().setdefault("gogorender", default_config)

class GogorenderConfigWdgt(QtGui.QWidget, ConfigurationWidget):
    name = name

    def setting(self, key):
        try:
            config = self.config()["gogorender"]
        except KeyError: config = {}

        if key == 'imgpath':
            return os.path.join(self.database().media_dir(), "_gogorender")
        else:
            return config.get(key, default_config[key])

    def __init__(self, component_manager, parent):
        ConfigurationWidget.__init__(self, component_manager)
        QtGui.QDialog.__init__(self, self.main_widget())
        vlayout = QtGui.QVBoxLayout(self)

        # add basic settings
        toplayout = QtGui.QFormLayout()

        self.not_render_char = QtGui.QLineEdit(self)
        self.not_render_char.setText(self.setting("not_render_char")[1:-1])
        toplayout.addRow(
            tr("Treat these characters normally:"), self.not_render_char)

        self.render_line_tags = QtGui.QLineEdit(self)
        self.render_line_tags.setText(self.setting("render_line_tags"))
        toplayout.addRow(
            tr("Render entire lines right-to-left for these tags:"),
            self.render_line_tags)

        self.max_line_width = QtGui.QSpinBox(self)
        self.max_line_width.setRange(50, 5000)
        self.max_line_width.setValue(int(self.setting('max_line_width')))
        toplayout.addRow(tr("Maximum line width (pixels):"),
                self.max_line_width)

        self.font_scaling = QtGui.QSpinBox(self)
        self.font_scaling.setRange(1, 1000)
        self.font_scaling.setValue(int(self.setting('font_scaling') * 100))
        toplayout.addRow(tr("Font scaling (percentage):"), self.font_scaling)

        self.transparent = QtGui.QCheckBox(self)
        self.transparent.setChecked(self.setting("transparent"))
        toplayout.addRow(tr("Render with transparency:"), self.transparent)

        self.default_render = QtGui.QCheckBox(self)
        self.default_render.setChecked(self.setting("default_render"))
        toplayout.addRow(tr("Render in Mnemosyne (for testing):"),
                         self.default_render)

        vlayout.addLayout(toplayout)

    def apply(self):
        was_default_render = self.setting('default_render')

        config = self.config()['gogorender']

        config["not_render_char"]  = u"[%s]" % unicode(self.not_render_char.text())
        config["render_line_tags"] = u"%s" % unicode(self.render_line_tags.text())
        config["transparent"]      = self.transparent.isChecked()
        config["default_render"]   = self.default_render.isChecked()
        config["max_line_width"]   = self.max_line_width.value()
        config["font_scaling"]     = float(self.font_scaling.value()) / 100.0

        imgpath = self.setting("imgpath")
        if os.path.exists(imgpath): shutil.rmtree(imgpath)
        if not os.path.exists(imgpath): os.mkdir(imgpath)

        for chain in render_chains:
            try:
                filter = self.render_chain(chain).filter(Gogorender)
                if filter:
                    filter.reconfigure()
            except KeyError: pass

        if was_default_render != config['default_render']:
            if was_default_render:
                self.render_chain('default').unregister_filter(Gogorender)
            else:
                self.render_chain('default').register_filter_at_back(
                        Gogorender, before=["ExpandPaths"])

def moveprev(pos):
    pos.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)

def movenext(pos):
    pos.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)

class Gogorender(Filter):
    name = name
    version = version
    tag_re = re.compile("(<[^>]*>)")

    def __init__(self, component_manager):
        Filter.__init__(self, component_manager)
        self.reconfigure()
        self.debug = component_manager.debug_file != None

        self.non_latin_font_size_increase = \
                self.config()["non_latin_font_size_increase"]

    def setting(self, key):
        try:
            config = self.config()["gogorender"]
        except KeyError: config = {}

        if key == 'imgpath':
            return os.path.join(self.database().media_dir(), "_gogorender")
        else:
            return config.get(key, default_config[key])

    def reconfigure(self):
        self.imgpath = self.setting('imgpath')
        if not os.path.exists(self.imgpath): os.mkdir(self.imgpath)

        self.transparent        = self.setting('transparent')
        self.render_char_re     = QRegExp(self.setting('render_char'))
        self.render_line_tags   = {t.strip()
                for t in self.setting('render_line_tags').split(',')}
        self.not_render_char_re = QRegExp(self.setting('not_render_char'))
        self.not_word_re        = QRegExp(not_word)
        self.not_line_re        = QRegExp(not_line)
        self.max_line_width     = int(self.setting('max_line_width'))

    def debugline(self, msg, pos):
        if self.debug:
            s = pos.selectedText()
            try:
                c = ord(unicode(s[-1]))
            except IndexError: c = 0
            self.component_manager.debug(
                u'gogorender: %s pos=%d char="%s" (0x%04x)'
                % (msg, pos.position(), s, c))

    # Must return one of:
    #   None            not rendered after all
    #   path            a path to the rendered image
    def render_word(self, word, font, color, render_rtol):
        fontname = font.family()
        fontsize = font.pointSize()

        style = ""
        if font.bold():   style += 'b'
        if font.italic(): style += 'i'

        colorname = color.name()[1:]

        # Generate a file name
        fword = word.replace('/', '_sl-')\
                    .replace('\\', '_bs-')\
                    .replace(' ', '_')\
                    .replace('#', '_ha-')\
                    .replace('{', '_cpo-')\
                    .replace('}', '_cpc-')\
                    .replace('*', '_ast-')
        if fword[0] == '.': fword = '_' + fword
        if fword[0] == '-': fword = '_' + fword

        filename = "%s-%s-%s-%s-%s" % (
            fword, fontname, str(fontsize), style, colorname)
        filename = md5(filename.encode("utf-8")).hexdigest() + ".png"
        path = os.path.join(self.imgpath, filename)
        relpath = "_gogorender" + "/" + filename

        if (os.path.exists(path)):
            return relpath

        # Render with Qt
        text = QtCore.QString(word)

        fm = QtGui.QFontMetrics(font)
        width = fm.width(text) + (fm.charWidth('M', 0) / 2)
        height = fm.height()

        option = QtGui.QTextOption()
        if render_rtol:
            lines = int(math.ceil(float(width) / float(self.max_line_width)))
            width = min(width, self.max_line_width)
            height = (height + fm.leading()) * lines
            option.setTextDirection(QtCore.Qt.RightToLeft)

        tbox = QtCore.QRectF(0, 0, width, height)

        # Alternative: calculate the bounding box from the text being rendered;
        #              disadvantage = bad alignment of adjacent images.
        #bbox = fm.boundingRect(text)
        #width = bbox.width()
        #height = bbox.height()

        if self.debug:
            self.component_manager.debug(
                "gogorender: rendering '%s' as a %dx%d image at %s"
                % (text, width, height, path))

        img = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)

        if self.transparent:
            img.fill(QtGui.qRgba(0,0,0,0))
        else:
            img.fill(QtGui.qRgba(255,255,255,255))

        p = QtGui.QPainter()
        p.begin(img)
        p.setBackgroundMode(QtCore.Qt.TransparentMode)
        p.setRenderHint(QtGui.QPainter.Antialiasing +
                        QtGui.QPainter.HighQualityAntialiasing +
                        QtGui.QPainter.SmoothPixmapTransform)
        p.setFont(font)
        p.setPen(QtGui.QColor(color))
        p.drawText(tbox, text, option)
        p.end()

        if img.save(path, "PNG"):
            return relpath
        else:
            return None

    # Must return one of:
    #   None            not rendered after all
    #   path            a path to the rendered image
    def render_html(self, word, html, font):
        filename = md5(word.encode("utf-8")).hexdigest() + "-html.png"
        path = os.path.join(self.imgpath, filename)
        relpath = "_gogorender" + "/" + filename

        if (os.path.exists(path)):
            return relpath

        text = QtCore.QString(word)
        fm = QtGui.QFontMetrics(font)
        width = fm.width(text) + (fm.charWidth('M', 0) / 2)

        # add 25% to the width
        lines = int(math.ceil((float(width) * 1.25) / float(self.max_line_width)))
        width = min(width, self.max_line_width)
        height = (fm.height() + fm.leading()) * lines

        # Render with Qt, adapted from:
        # http://www.qtcentre.org/threads/11357-HTML-text-drawn-with-QPainter-drawText()
        doc = QTextDocument()
        doc.setUndoRedoEnabled(False)
        doc.setHtml(html)
        doc.setTextWidth(width)
        doc.setDocumentMargin(0.0)
        doc.setIndentWidth(0.0)
        doc.setUseDesignMetrics(True)
        doc.setDefaultFont(font)

        option = QtGui.QTextOption()
        option.setTextDirection(QtCore.Qt.RightToLeft)

        tbox = QtCore.QRectF(0, 0, width, height)

        if self.debug:
            self.component_manager.debug(
                "gogorender: rendering '%s' as a %dx%d image at %s"
                % (word, width, height, path))

        img = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)
        if self.transparent:
            img.fill(QtGui.qRgba(0,0,0,0))
        else:
            img.fill(QtGui.qRgba(255,255,255,255))

        p = QtGui.QPainter()
        p.begin(img)
        p.setBackgroundMode(QtCore.Qt.TransparentMode)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        doc.drawContents(p, tbox)
        p.end()

        if img.save(path, "PNG"):
            return relpath
        else:
            return None

    def substitute(self, text, mapping):
        r = []
        for s in self.tag_re.split(text):
            if len(s) == 0 or s[0] == '<':
                r.append(s)
                continue

            while mapping:
                (match, path) = mapping[0]

                (before, x, after) = s.partition(match)
                if x == '':
                    s = before
                    break
                
                r.append(before)
                r.append('<img src="%s"/>' % path)
                mapping = mapping[1:]
                s = after

            r.append(s)

        return ''.join(r)

    def run(self, text, card, fact_key, **render_args):
        doc = QTextDocument()
        doc.setUndoRedoEnabled(False)
        doc.setDocumentMargin(0.0)
        doc.setIndentWidth(0.0)
        doc.setUseDesignMetrics(True)
        doc_modified = False

        proxy_key = card.card_type.fact_key_format_proxies()[fact_key]
        font_string = self.config().card_type_property(
            "font", card.card_type, proxy_key)

        if font_string:
            family,size,x,x,weight,italic,u,s,x,x = font_string.split(",")
            font = QtGui.QFont(family, int(size), int(weight), bool(int(italic)))
            doc.setDefaultFont(font)

        if {True for t in card.tags if t.name in self.render_line_tags}:
            render_line = True
            not_word_re = self.not_line_re
        else:
            render_line = False
            not_word_re = self.not_word_re

        doc.setHtml(text)
        if self.debug:
            self.component_manager.debug(
                "gogorender: %s\ngogorender: %s\ngogorender: %s"
                % (70 * "-", text, 70 * "-"))

        render = []
        pos = doc.find(self.render_char_re)
        while not pos.isNull():
            s = pos.selectedText()
            if (self.not_render_char_re.exactMatch(s)
                    or not_word_re.exactMatch(s)):
                self.debugline("skip", pos)
                movenext(pos)
                pos = doc.find(self.render_char_re, pos)
                continue;
            self.debugline("===", pos)

            fmt = pos.charFormat()
            font = fmt.font()
            color = fmt.foreground().color()

            # find the start of the word
            #moveprev(pos)
            while not pos.atBlockStart():
                moveprev(pos)
                s = pos.selectedText()
                ccolor = pos.charFormat().foreground().color()
                self.debugline("<--", pos)

                if len(s) > 0 and not_word_re.exactMatch(s[0]):
                    movenext(pos)
                    self.debugline("-->", pos)
                    break;

                if (not render_line and
                        (pos.charFormat().font() != font or ccolor != color)):
                    break;

            pos.setPosition(pos.position(), QTextCursor.MoveAnchor)

            # find the end of the word
            while not pos.atBlockEnd():
                movenext(pos)
                s = pos.selectedText()
                ccolor = pos.charFormat().foreground().color()
                self.debugline("-->", pos)

                if ((not render_line and
                           (pos.charFormat().font() != font or ccolor != color))
                        or not_word_re.exactMatch(s[-1])):
                    moveprev(pos)
                    self.debugline("<-)", pos)
                    break;

            if pos.hasSelection():
                word = unicode(pos.selectedText())

                if self.debug:
                    self.component_manager.debug(
                        u'gogorender: word="%s"' % word)

                font.setPointSizeF((font.pointSize() +
                                    self.non_latin_font_size_increase)
                                   * self.setting('font_scaling'))

                if render_line:
                    html = unicode(pos.selection().toHtml())
                    path = self.render_html(word, html, font)
                else:
                    path = self.render_word(word, font, color, render_line)

                if path is not None:
                    if render_line:
                        pos.removeSelectedText()
                        pos.insertImage(path)
                        doc_modified = True
                    else:
                        render.append((word, unicode(path)))

            pos = doc.find(self.render_char_re, pos)

        if doc_modified:
            text = body_match_re.sub(r'\g<body>', unicode(doc.toHtml()))
        elif render:
            text = self.substitute(unicode(text), render)

        return text

class GogorenderPlugin(Plugin):
    name = name
    description = (tr("Render words as image files on Mnemogogo export.") +
                   " (v" + version + ")")
    components = [GogorenderConfig, GogorenderConfigWdgt, Gogorender]

    def __init__(self, component_manager):
        Plugin.__init__(self, component_manager)

    def activate(self):
        Plugin.activate(self)

        try:
            if self.config()['gogorender']['default_render']:
                render_chains.append('default')
        except KeyError: pass

        for chain in render_chains:
            try:
                self.new_render_chain(chain)
            except KeyError: pass

    def deactivate(self):
        Plugin.deactivate(self)
        for chain in render_chains:
            try:
                self.render_chain(chain).unregister_filter(Gogorender)
            except KeyError: pass

    def new_render_chain(self, name):
        if name in render_chains:
            self.render_chain(name).register_filter_at_back(
                    Gogorender, before=["ExpandPaths"])

# Register plugin.

from mnemosyne.libmnemosyne.plugin import register_user_plugin
register_user_plugin(GogorenderPlugin)

