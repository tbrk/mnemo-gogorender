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

try:
    from mnemosyne.core import *
    mnemosyne_version = 1

    from qt import *
    import sys
    import re
    from copy import copy
    import os, os.path

except ImportError:
    mnemosyne_version = 2

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

name = "Gogorender"
version = "2.0"
description = "Render words as image files on Mnemogogo export. (v" + version + ")"

render_chains = ["mnemogogo"]

##############################################################################
# Mnemosyne 1.x
if mnemosyne_version == 1:

    # Basic use
    # ---------
    # Save this file into the Mnemosyne plugins directory
    # ($HOME/.mnemosyne/plugins) and start Mnemosyne. In the next Mnemogogo
    # export, all words that contain non-latin characters should be exported
    # as img files.
    #
    # Intermediate use
    # ----------------
    # Edit the config.py file that exists under the Mnemosyne home directory
    # ($HOME/.mnemosyne), and add lines similar too:
    # gogorender = {
    #   'size' : 48,
    #   'font' : 'DejaVu Sans'
    # }
    #
    # Valid options include:
    #       size                    font size (defaults to 12)
    #       font                    font (defaults to Mnemosyne QA font)
    #       <categoryname>.size     size per category
    #       <categoryname>.font     font per category
    #       reignore                regular expression for matching character
    #                               sequences that should be ignored (not
    #                               considered as words).
    #       imgpath                 the path for saving images, defaults to
    #                               'gogorender' in the Mnemosyne home
    #                               directory.
    #       clear_imgpath           clear the image path on startup
    #                               (defaults to True)
    #       render_match            only non-latin1 characters that match this
    #                               regular expression are considered for
    #                               rendering.
    #                               Defaults to '.', i.e. all characters.
    #       dont_render             a unicode string containing all non-latin-1
    #                               characters that should not trigger
    #                               rendering (You may need to change the top
    #                               line of config.py to:
    #                                # encoding: utf-8
    #                                to avoid a compilation error.)
    #                               This filter is applied after render_match.
    #       transparent             transparent background? (default: true)
    #       <categoryname>.ignore   exclude certain categories
    #
    # Advanced use
    # ------------
    # Write your own functions to decide whether and how to render words:
    #
    # There are two options (for config.py)
    #       font_fn                 the name of a function that is called for
    #                               each word to decide whether to render it,
    #                               and which font and size to use. This may
    #                               be a full path, e.g. 'mymodule.name', or
    #                               a function name (NOT the function itself)
    #                               in either gogorender.py or config.py.
    #       split_fn                the name of a function called to break
    #                               text up into words for rendering (or not).
    #       render_fn               the name of a function that is called to
    #                               render a word as an image.
    #
    # See the 'choose_font', 'split_text', and 'render_word' functions in this
    # file for examples, and the required interface.
    #
    ###########################################################################

    # Must return one of:
    #   None            do not render the given word
    #   (size, font)    a font size (integer) and name to use in rendering the
    #                   given word
    def choose_font(word, category, config):
        if config['%s.ignore' % category]:
            return None

        render_match_re = config['render_match_re']
        dont_render = config.get('dont_render', u"")

        # 1. decide whether to render
        render = False
        for c in word:
            if ((ord(c) > 255) and render_match_re.match(c) and (c not in dont_render)):
                render = True
                break

        if not render:
            return None

        # 2. choose a font

        font = config["%s.font" % category]
        if font is None:
            font = get_config("QA_font")

        try:
            size = int(config["%s.size" % category])
        except (ValueError, TypeError):
            size = config["size"]

        return (size, font)

    # Split the given text into pieces, the font choice and render functions
    # will be called against each piece. The text will never contain html tags.
    wsregex = re.compile(r'([ \t\n]+)', re.MULTILINE)

    def simple_split(text, category, config):
        return wsregex.split(text)

    def list_split(text, category, config):
        return list(text)

    # This splitter groups words that would be rendered with the same font,
    # including the spaces between them. It does not group across line
    # breaks. This approach has two main advantages:
    #  * Less individual image files, and thus less security prompts.
    #  * Proper rendering of right-to-left scripts (like Arabic and Hebrew).
    # and two main disadvantages:
    #  * Less individual image files, and thus less opportunity for
    #    line-breaking; Mnemogogo will instead scale images.
    #  * The function is more complex.
    def split_text(text, category, config):
        font_fn = config.get_function('font_fn')

        def classify_word(word, category=category, config=config):
            if wsregex.match(word):
                if '\n' in word:
                    return 'X-newline'
                return 'space'
            f = font_fn(word, category, config)
            if f is None:
                return 'norender'
            return '%d-%s' % f

        wordlist = wsregex.split(text)
        wordlist.append(None)

        r = []
        prev = 'X-first'
        space = []
        words = []
        for word in wordlist:
            if word is None:
                curr = 'X-last'
            else:
                curr = classify_word(word)

            if (curr == 'space') and (prev != 'space'):
                if words == []:
                    words.append(word)
                    prev = curr
                else:
                    space.append(word)
                continue

            if (curr == prev) and (curr[0] != 'X'):
                words.extend(space)
                space = []
                words.append(word)
            else:
                r.append(''.join(words))
                if space != []:
                    r.append(''.join(space))
                    space = []
                words = [word]
                prev = curr

        return r

    def drawtext(width, height, font, color, text, path):
        pix = QPixmap(width, height)
        pix.fill(QColor('white'))

        p = QPainter()
        p.begin(pix)
        p.setFont(font)
        p.setPen(QColor(color))
        p.drawText(0, 0, width, height, 0, text)
        p.end()

        if pix.save(path, "PNG"):
            return path
        else:
            return None

    def transtext(width, height, font, color, text, path):
        pix = QPixmap(width, height)
        pix.fill(QColor('black'))

        p = QPainter()
        p.begin(pix)
        p.setFont(font)
        p.setPen(QColor(255,0,0)) # all red
        p.drawText(0, 0, width, height, 0, text)
        p.end()

        img = pix.convertToImage()
        img.setAlphaBuffer(1)

        c = QColor(color)
        r = qRed(c.rgb())
        b = qBlue(c.rgb())
        g = qGreen(c.rgb())

        for x in range(0, img.width()):
            for y in range(0, img.height()):
                pix = img.pixel(x, y)
                img.setPixel(x, y, qRgba(r, b, g, qRed(pix)))

        if img.save(path, "PNG"):
            return path
        else:
            return None

    # Must return one of:
    #   None            not rendered after all
    #   path            a path to the rendered image
    # config will contain
    #  style            a string with 'b' for bold and 'i' for italic
    #  color            current color
    #  transparent      a boolean
    def render_word(word, category, config, fontsize, font):
        # 1. Working out the Qt-specific font details (and for filename)
        style = ""
        weight = QFont.Normal
        if ('b' in config['style']):
            weight = QFont.Bold
            style = style + "b"

        italic = False
        if ('i' in config['style']):
            italic = True
            style = style + "i"

        if font is None:
            font = "Helvetica"

        # 2. Generate a file name
        fword = word.replace('/', '_sl-').replace('\\', '_bs-').replace(' ', '_')
        if fword[0] == '.': fword = '-' + fword

        filename = "%s-%s-%s-%s-%s.png" % (
            fword.encode('punycode'), font.replace(' ', '_'),
                str(fontsize), style, config['color'])
        path = os.path.join(config['imgpath'], filename)

        if (os.path.exists(path)):
            return path

        # 3. Render with Qt
        text = QString(word)

        font = QFont(font, fontsize, weight, italic)
        fm = QFontMetrics(font)

        width = fm.width(text) + (fm.charWidth('M', 0) / 2)
        height = fm.height()

        # Alternative: calculate the bounding box from the text being rendered;
        #              disadvantage = bad alignment of adjacent images.
        #bbox = fm.boundingRect(text)
        #width = bbox.width()
        #height = bbox.height()

        if config.get('transparent', True):
            r = transtext(width, height, font, config['color'], text, path)
        else:
            r = drawtext(width, height, font, config['color'], text, path)

        return r
        
    class Config:
        def __init__(self):

            try: config = copy(get_config(name))
            except KeyError:
                set_config(name, {})
                config = {}

            defaults = {
                'font' : None,
                'size' : '12',
                'reignore' : r'[()]',
                'basedir' : get_basedir(),
                'imgpath' : os.path.join(get_basedir(), name),
                'font_fn' : 'choose_font',
                'split_fn' : 'split_text',
                'render_fn' : 'render_word',
                'clear_imgpath' : True,
                'transparent' : True,
            }

            for (setting, default) in defaults.iteritems():
                if not config.has_key(setting):
                    config[setting] = default

            self.config = config

        def get_function(self, key):
            fullname = self.config[key]
            nms = fullname.rsplit('.', 1)

            try:
                if len(nms) == 1:
                    try:
                        r = globals()[nms[0]]
                        return r
                    except:
                        nms.insert(0, 'config')

                [modulenm, funcnm] = nms
                module = __import__(modulenm, globals(), locals(), [], -1)
                return getattr(module, funcnm)

            except Exception, e:
                logger.error(
                    "%s: cannot find function '%s' (%s)" % (name, fullname, e))

            return None

        def has_key(self, key):
            return self.config.has_key(key)

        def get(self, key, default):
            if self.config.has_key(key):
                return self.config[key]
            return default

        def __getitem__(self, key):
            if self.config.has_key(key):
                return self.config[key]

            basekey = key.split('.', 1)[-1]
            if self.config.has_key(basekey):
                return self.config[basekey]

            return None

        def __setitem__(self, key, value):
            self.config[key] = value

        def __delitem__(self, key):
            del self.config[key]

        def keys(self):
            return self.config.keys()

    class Splitter:
        color_att = r'(\scolor\s*=\s*"(?P<color>[^"]+)")'
        style_att = r'(\sstyle\s*=\s*"(?P<style>[^"]+)")'
        other_att = r'(\s\w+\s*=\s*"[^"]+")'
        ignore_tag = (r'(<\s*(?P<tag>/\w*|\w+)('
                      + color_att
                      + r'|' + style_att
                      + r'|' + other_att
                      + ')*\s*/?>)')

        def __init__(self, text, category, split_fn, config):
            extra_ignore = ''
            if config['reignore'] != '':
                extra_ignore = r'(%s)|' % config['reignore']

            ignore_re_text = (r'(?P<ignore>&#?[A-Za-z0-9]+;|'
                              + extra_ignore + self.ignore_tag + r')(?P<rest>.*)')
            self.ignore_re = re.compile(ignore_re_text,
                re.IGNORECASE + re.MULTILINE + re.DOTALL + re.UNICODE)

            self.state = {
                'color' : ['black'],
                'style' : [],
            }
            self.curr = []
            self.words = []

            self.category = category
            self.text = text
            self.split_fn = split_fn
            self.config = config

        def __iter__(self):
            return self

        def short_state(self):
            style = self.state['style'][-2:]
            style.reverse()

            return {
                'color' : self.state['color'][-1],
                'style' : ''.join(style)
            }

        def process_style(self, text):
            stylepairs = text.split(";")
            d = {}
            for sp in stylepairs:
                try:
                    name, value = sp.split(":", 1)
                    d[name.strip().lower()] = value.strip()
                except:
                    pass
            return d

        def split_curr(self):
            curr = ''.join(self.curr)
            self.curr = []

            self.words = self.split_fn(curr, self.category, self.config)
            if self.words == []:
                self.words = [curr]
            self.words.reverse()

            return (self.words.pop(), self.short_state())

        def next(self):
            if self.words != []:
                return (self.words.pop(), self.short_state())

            if self.text == '':
                if len(self.curr) > 0:
                    return self.split_curr()
                raise StopIteration

            r = self.ignore_re.match(self.text)

            # keep building word
            if not r:
                self.curr.append(self.text[0])
                self.text = self.text[1:]
                return self.next()

            # return word
            if self.curr != []:
                return self.split_curr()

            # ignore element (track state)
            tag = r.group('tag')
            if tag:
                if (tag == 'u'):
                    tag = 'i'
                elif (tag == '/u'):
                    tag = '/i'

                if (tag == 'i') or (tag == 'b'):
                    self.state['style'].append(tag)

                elif (tag == '/i') or (tag == '/b'):
                    try:
                        self.state['style'].pop()
                    except IndexError:
                        pass

                elif tag == 'font':
                    if r.group('color'):
                        self.state['color'].append(r.group('color'))
                    else:
                        self.state['color'].append(self.state['color'][-1])

                elif tag == 'span':
                    style = self.process_style(r.group('style'))
                    if style.has_key('color'):
                        self.state['color'].append(style['color'])
                    else:
                        self.state['color'].append(self.state['color'][-1])

                elif (((tag == '/font') or (tag == '/span'))
                      and (len(self.state['color']) > 0)):
                    try:
                        self.state['color'].pop()
                    except IndexError:
                        pass

            self.text = r.group('rest')
            return (r.group('ignore'), None)

    def test_splitter():
        splitter = Splitter(sys.stdin.read(), 'test', split_text, Config())
        for (word, state) in splitter:
            if state:
                print ("'%s' (style=%s color=%s)" % (word, state['style'], state['color']))
            else:
                print ("'%s' (ignore)" % word)


    class Gogorender(Plugin):

        def description(self):
            return ("Render segments of text as image files. (v" +
                    version + ")")

        def load(self):
            logger.info("%s: version %s" % (name, version))

            self.config = Config()
            imgpath = self.config['imgpath']
            self.config['render_match_re'] = re.compile(
                    self.config.get('render_match', r'.'), re.DOTALL)

            if self.config['clear_imgpath'] and os.path.exists(imgpath):
                for file in os.listdir(imgpath):
                    filepath = os.path.join(imgpath, file)
                    try:
                        if os.path.isfile(filepath):
                            os.unlink(filepath)
                    except:
                        pass

            if not os.path.exists(imgpath):
                os.mkdir(imgpath)

            self.format_mnemosyne = (
                    self.config.has_key('mnemosyne.font_fn')
                and self.config.has_key('mnemosyne.split_fn')
                and self.config.has_key('mnemosyne.render_fn'))

            if (self.format_mnemosyne):
                register_function_hook("filter_q", self.mnemosyne_format)
                register_function_hook("filter_a", self.mnemosyne_format)

            self.format_mnemogogo = (
                    self.config.has_key('font_fn')
                and self.config.has_key('split_fn')
                and self.config.has_key('render_fn'))

            if (self.format_mnemogogo):
                register_function_hook("gogo_q", self.mnemogogo_format)
                register_function_hook("gogo_a", self.mnemogogo_format)

        def unload(self):
            if (self.format_mnemosyne):
                unregister_function_hook("filter_q", self.format)
                unregister_function_hook("filter_a", self.format)

            if (self.format_mnemogogo):
                unregister_function_hook("gogo_q", self.format)
                unregister_function_hook("gogo_a", self.format)
        
        def mnemosyne_format(self, text, card):
            return self.format(text, card,
                               self.config.get_function('mnemosyne.font_fn'),
                               self.config.get_function('mnemosyne.split_fn'),
                               self.config.get_function('mnemosyne.render_fn'))

        def mnemogogo_format(self, text, card):
            return self.format(text, card,
                               self.config.get_function('font_fn'),
                               self.config.get_function('split_fn'),
                               self.config.get_function('render_fn'))

        def format(self, text, card, font_fn, split_fn, render_fn):

            if (font_fn is None) or (render_fn is None):
                return text

            splitter = Splitter(text, card.cat.name, split_fn, self.config)

            r = []
            for (word, state) in splitter:
                if (not state):
                    r.append(word)
                    continue

                for (key, value) in state.iteritems():
                    self.config[key] = value

                try:
                    font = font_fn(word, card.cat.name, self.config)
                except Exception, e:
                    logger.error("%s: failure in font_fn: %s" % (name, str(e)))
                    font = None

                if font is None:
                    r.append(word)
                    continue

                (size, fontname) = font

                try:
                    path = render_word(word, card.cat.name, self.config,
                                       size, fontname)
                except Exception, e:
                    logger.error("%s: failure in render_word: %s" % (name, str(e)))
                    path = None

                if path is None:
                    r.append(word)
                else:
                    r.append('<img src="%s"/>' % path)

            return ''.join(r)

    p = Gogorender()
    p.load()

##############################################################################
# Mnemosyne 2.x
elif mnemosyne_version == 2:

    debug = False

    default_config = {
        'transparent'     : True,
        'render_char'     : u'[\u0100-\uff00]',
        'not_render_char' : u'[—≠–œ‘’“”…€]',

        # \xfffc is the "Object Replacement Character" (used for images)
        # \x2028 is the "Line Separator"
        # \x2029 is the "Paragraph Separator"
        'not_word'        : u'[\s\u2028\u2029\ufffc]',
    }

    def translate(text):
        return text

    class GogorenderConfig(Hook):
        used_for = "configuration_defaults"

        def run(self):
            self.config().setdefault("gogorender", default_config)

    class GogorenderConfigWdgt(QtGui.QWidget, ConfigurationWidget):
        name = name

        def __init__(self, component_manager, parent):
            ConfigurationWidget.__init__(self, component_manager)
            QtGui.QDialog.__init__(self, self.main_widget())
            vlayout = QtGui.QVBoxLayout(self)

            config = self.config()['gogorender']

            # add basic settings
            toplayout = QtGui.QFormLayout()

            self.not_render_char = QtGui.QLineEdit(self)
            self.not_render_char.setText(config["not_render_char"][1:-1])
            toplayout.addRow(
                translate("Treat these characters normally:"),
                self.not_render_char)

            self.transparent = QtGui.QCheckBox(self)
            self.transparent.setChecked(config["transparent"])
            toplayout.addRow(translate("Render with transparency:"), self.transparent)

            vlayout.addLayout(toplayout)

        def apply(self):
            self.config()["gogorender"]["not_render_char"] = \
                u"[%s]" % unicode(self.not_render_char.text())
            self.config()["gogorender"]["transparent"] = \
                self.transparent.isChecked()

            for chain in render_chains:
                try:
                    filter = self.render_chain(chain).filter(Gogorender)
                    filter.reconfigure()
                except KeyError: pass

    def moveprev(pos):
        pos.movePosition(QTextCursor.PreviousCharacter, QTextCursor.KeepAnchor)

    def movenext(pos):
        pos.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)

    def debugline(msg, pos):
        if debug:
            s = pos.selectedText()
            try:
                c = ord(unicode(s[0]))
            except IndexError: c = 0
            print u'%s pos=%d char="%s" (0x%04x)' % (msg, pos.position(), s, c)

    class Gogorender(Filter):
        name = name
        version = version

        def __init__(self, component_manager):
            Filter.__init__(self, component_manager)
            self.reconfigure()

        def setting(self, key):
            try:
                config = self.config()["gogorender"]
            except KeyError: config = {}

            if key == 'imgpath':
                return config.get('imgpath',
                    os.path.join(self.config().data_dir, 'gogorender'))
            else:
                return config.get(key, default_config[key])

        def reconfigure(self):
            self.imgpath = self.setting('imgpath')
            if not os.path.exists(self.imgpath): os.mkdir(self.imgpath)

            self.transparent        = self.setting('transparent')
            self.render_char_re     = QRegExp(self.setting('render_char'))
            self.not_render_char_re = QRegExp(self.setting('not_render_char'))
            self.not_word_re        = QRegExp(self.setting('not_word'))

        # Must return one of:
        #   None            not rendered after all
        #   path            a path to the rendered image
        def render_word(self, word, font, color):
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

            filename = "%s-%s-%s-%s-%s.png" % (
                fword, fontname, str(fontsize), style, colorname)
            path = os.path.join(self.imgpath, filename)

            if (os.path.exists(path)):
                return path

            # Render with Qt
            text = QtCore.QString(word)

            fm = QtGui.QFontMetrics(font)
            width = fm.width(text) + (fm.charWidth('M', 0) / 2)
            height = fm.height()

            # Alternative: calculate the bounding box from the text being rendered;
            #              disadvantage = bad alignment of adjacent images.
            #bbox = fm.boundingRect(text)
            #width = bbox.width()
            #height = bbox.height()

            img = QtGui.QImage(width, height, QtGui.QImage.Format_ARGB32)

            if self.transparent:
                img.fill(QtGui.qRgba(0,0,0,0))
            else:
                img.fill(QtGui.qRgba(255,255,255,255))

            p = QtGui.QPainter()
            p.begin(img)
            p.setFont(font)
            p.setPen(QtGui.QColor(color))
            p.drawText(0, 0, width, height, 0, text)
            p.end()

            if img.save(path, "PNG"):
                return path
            else:
                return None

        def run(self, text, card, fact_key, **render_args):
            doc = QTextDocument()
            doc.setHtml(text)
            if debug: print "%s\n%s\n%s" % (70 * "-", text, 70 * "-")

            pos = doc.find(self.render_char_re)
            while not pos.isNull():
                s = pos.selectedText()
                if (self.not_render_char_re.exactMatch(s)
                        or self.not_word_re.exactMatch(s)):
                    debugline("skip", pos)
                    movenext(pos)
                    pos = doc.find(self.render_char_re, pos)
                    continue;
                debugline("==", pos)

                fmt = pos.charFormat()
                font = fmt.font()
                color = fmt.foreground().color()

                # find the start of the word
                #moveprev(pos)
                while not pos.atBlockStart():
                    moveprev(pos)
                    s = pos.selectedText()
                    ccolor = pos.charFormat().foreground().color()
                    debugline("<--", pos)

                    if len(s) > 0 and self.not_word_re.exactMatch(s[0]):
                        movenext(pos)
                        debugline("-->", pos)
                        break;

                    if pos.charFormat().font() != font or ccolor != color:
                        break;

                pos.setPosition(pos.position(), QTextCursor.MoveAnchor)

                # find the end of the word
                while not pos.atBlockEnd():
                    movenext(pos)
                    s = pos.selectedText()
                    ccolor = pos.charFormat().foreground().color()
                    debugline("-->", pos)

                    if (pos.charFormat().font() != font or ccolor != color
                            or self.not_word_re.exactMatch(s[-1])):
                        moveprev(pos)
                        debugline("<--)", pos)
                        break;

                if pos.hasSelection():
                    word = pos.selectedText()
                    if debug: print u'word="%s"' % word
                    path = self.render_word(unicode(word), font, color)

                    if path is not None:
                        pos.removeSelectedText()
                        pos.insertHtml('<img src="%s"/>' % path)

                pos = doc.find(self.render_char_re, pos)

            return unicode(doc.toHtml())

    class GogorenderPlugin(Plugin):
        name = name
        description = description
        components = [GogorenderConfig, GogorenderConfigWdgt, Gogorender]

        def __init__(self, component_manager):
            Plugin.__init__(self, component_manager)

        def activate(self):
            Plugin.activate(self)
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
                self.render_chain(name).register_at_back(Gogorender)

    # Register plugin.

    from mnemosyne.libmnemosyne.plugin import register_user_plugin
    register_user_plugin(GogorenderPlugin)

