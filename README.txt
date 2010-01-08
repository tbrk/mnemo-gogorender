gogorender.py <timbob@bigpond.com>

Plugin for rendering segments of text as image files.

The main reason for this plugin is to work around the limitations of
displaying fonts under J2ME on certain mobile phones. Characters can instead
be rendered on a PC where more fonts and libraries are available.

NB: On phones where security prompts cannot be disabled, each image will
    generate a confirmation prompt. This can quickly become annoying.

Basic use
---------
Save this file into the Mnemosyne plugins directory
($HOME/.mnemosyne/plugins) and start Mnemosyne. In the next Mnemogogo
export, all words that contain non-latin characters should be exported as
img files.

Intermediate use
----------------
Edit the config.py file that exists under the Mnemosyne home directory
($HOME/.mnemosyne), and add lines similar too:
gogorender = {
  'size' : 48,
  'font
}

Valid options include:
	size			font size (defaults to 12)
	font			font (defaults to Mnemosyne QA font)
	<categoryname>.size	size per category
	<categoryname>.font	font per category
	ignore			regular expression for matching character
				sequences that should be ignored (not
				considered as words).
	imgpath			the path for saving images, defaults to
				'gogorender' in the Mnemosyne home
				directory.
	clear_imgpath		clear the image path on startup
				(defaults to True)
	<categoryname>.ignore	exclude certain categories

Advanced use
------------
Write your own functions to decide whether and how to render words:

There are two options (for config.py)
	font_fn			the name of a function that is called for
				each word to decide whether to render it,
				and which font and size to use. This may
				be a full path, e.g. 'mymodule.name', or
				a function name (NOT the function itself)
				in either gogorender.py or config.py.
	render_fn		the name of a function that is called to
				render a word as an image.

See the 'choose_font' and 'render_word' functions in this file for examples,
and the required interface.

Please report any bugs to timbob@bigpond.com.

