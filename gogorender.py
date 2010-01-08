##############################################################################
#
# gogorender.py
# Timothy Bourke <timbob@bigpond.com>
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
#   'font
# }
#
# Valid options include:
#	size			font size (defaults to 12)
#	font			font (defaults to Mnemosyne QA font)
#	<categoryname>.size	size per category
#	<categoryname>.font	font per category
#	ignore			regular expression for matching character
#				sequences that should be ignored (not
#				considered as words).
#	imgpath			the path for saving images, defaults to
#				'gogorender' in the Mnemosyne home
#				directory.
#	clear_imgpath		clear the image path on startup
#				(defaults to True)
#	<categoryname>.ignore	exclude certain categories
#
# Advanced use
# ------------
# Write your own functions to decide whether and how to render words:
#
# There are two options (for config.py)
#	font_fn			the name of a function that is called for
#				each word to decide whether to render it,
#				and which font and size to use. This may
#				be a full path, e.g. 'mymodule.name', or
#				a function name (NOT the function itself)
#				in either gogorender.py or config.py.
#	render_fn		the name of a function that is called to
#				render a word as an image.
#
# See the 'choose_font' and 'render_word' functions in this file for
# examples, and the required interface.
#
##############################################################################

from mnemosyne.core import *
from qt import *
import sys
import re
from copy import copy
import os, os.path
from PIL import Image, ImageDraw, ImageFont

name = "gogorender"
version = "0.9.0"

def choose_font(word, category, config):

    if config['%s.ignore' % category]:
	return None

    # 1. decide whether to render
    render = False
    for c in word:
	if ord(c) > 255: # render any non-Latin-1 characters
	    render = True
	    break

    if not render:
	return None

    # 2. choose a font

    font = config["%s.font" % category]
    if font is None:
	font = get_config("QA_font")

    return (int(config["%s.size" % category]), font)

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
    fword = word.replace('/', '_sl-').replace('\\', '_bs-')
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
    
    pix = QPixmap(width, height)
    pix.fill(QColor('white'))

    p = QPainter()
    p.begin(pix)
    p.setFont(font)
    p.setPen(QColor(config['color']))
    p.drawText(0, 0, width, height, 0, text)
    p.end()

    if pix.save(path, "PNG"):
	return path
    else:
	return None

class Config:
    def __init__(self):

	try: config = copy(get_config(name))
	except KeyError:
	    set_config(name, {})
	    config = {}
	
	defaults = {
	    'font' : None,
	    'size' : '12',
	    'ignore' : r'[()]',
	    'basedir' : get_basedir(),
	    'imgpath' : os.path.join(get_basedir(), name),
	    'font_fn' : 'choose_font',
	    'render_fn' : 'render_word',
	    'clear_imgpath' : True,
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

    def __init__(self, text, config):
	extra_ignore = ''
	if config['ignore'] != '':
	    extra_ignore = r'(%s)|' % config['ignore']

	ignore_re_text = (r'(?P<ignore>\s+|&#?[A-Za-z0-9]+;|'
			  + extra_ignore + self.ignore_tag + r')(?P<rest>.*)')
	self.ignore_re = re.compile(ignore_re_text,
	    re.IGNORECASE + re.MULTILINE + re.DOTALL + re.UNICODE)

	self.state = {
	    'color' : ['black'],
	    'style' : [],
	}
	self.word = []
	self.text = text

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

    def return_word(self):
	word = ''.join(self.word)
	self.word = []
	return (word, self.short_state())

    def next(self):
	if self.text == '':
	    if len(self.word) > 0:
		return self.return_word()
	    raise StopIteration

	r = self.ignore_re.match(self.text)

	# keep building word
	if not r:
	    self.word.append(self.text[0])
	    self.text = self.text[1:]
	    return self.next()
	
	# return word
	if self.word != []:
	    return self.return_word()

	# ignore element (track state)
	tag = r.group('tag')
	if tag:
	    if (tag == 'i') or (tag == 'b'):
		self.state['style'].append(tag)

	    elif (tag == '/i') or (tag == '/b'):
		self.state['style'].pop()

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
		self.state['color'].pop()
	
	self.text = r.group('rest')
	return (r.group('ignore'), None)

def test_splitter():
    splitter = Splitter(sys.stdin.read(), Config())
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
	    and self.config.has_key('mnemosyne.render_fn'))

	if (self.format_mnemosyne):
	    register_function_hook("filter_q", self.mnemosyne_format)
	    register_function_hook("filter_a", self.mnemosyne_format)

	self.format_mnemogogo = (
	        self.config.has_key('font_fn')
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
			   self.config.get_function('mnemosyne.render_fn'))

    def mnemogogo_format(self, text, card):
	return self.format(text, card,
			   self.config.get_function('font_fn'),
			   self.config.get_function('render_fn'))

    def format(self, text, card, font_fn, render_fn):

	if (font_fn is None) or (render_fn is None):
	    return text

	splitter = Splitter(text, self.config)

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

