import AppKit
import CoreText
import io
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.tables._g_l_y_f import Glyph as FontToolsGlyph

from lib.UI.spaceCenter.glyphSequenceEditText import *


_dummyGlyph = FontToolsGlyph()

LTR = 0
RTL = 1


def mergeUnicodeStack(glyphNames, stack, cmap, glyphOrder, direction, data, ftFont):
    if not stack:
        return
    if len(stack) > 1:
        # cache this...
        fontProvider = CoreText.CGDataProviderCreateWithCFData(data)
        cgFont = CoreText.CGFontCreateWithDataProvider(fontProvider)
        ctFont = CoreText.CTFontCreateWithGraphicsFont(cgFont, 0, None, None)
        attributes = {
            AppKit.NSFontAttributeName: ctFont
        }
        if direction == RTL:
            attributes[AppKit.NSWritingDirectionAttributeName] = [AppKit.NSWritingDirectionRightToLeft | AppKit.NSTextWritingDirectionEmbedding]
        attr = AppKit.NSAttributedString.alloc().initWithString_attributes_("".join(stack), attributes)
        ctLine = CoreText.CTLineCreateWithAttributedString(attr)
        ctRuns = CoreText.CTLineGetGlyphRuns(ctLine)
        newGlyphNames = []
        for ctRun in ctRuns:
            glyphCount = CoreText.CTRunGetGlyphCount(ctRun)
            indexes = CoreText.CTRunGetGlyphs(ctRun, (0, glyphCount), None)
            for index in indexes:
                glyphName = ftFont.getGlyphName(index)
                newGlyphNames.append(glyphName)
        if direction == RTL:
            newGlyphNames.reverse()
        glyphNames.extend(newGlyphNames)
    else:
        glyphNames.extend([characterToGlyphName(c, cmap, fallback=c) for c in stack])


def splitText(text, cmap, groups=dict(), allowShapingWithGlyphs=None, direction=0, fontData=None, fontObject=None):
    """
    Convert a given string to a set of glyph names
    based on the a given `text` for a `cmap`

    Optionally a `groups` dictionary can be provided.
    """
    if text is None:
        return []
    # escape //
    text = text.replace("//", "/slash ")
    text = text.replace(f"{currentGlyphKey} ", currentGlyphKey)
    text = text.replace(f"{currentSelectionKey} ", currentSelectionKey)
    glyphNames = []
    compileStack = None
    unicodeStack = []

    for lineNumber, newLine in enumerate(text.split(newLineKey)):

        if lineNumber > 0:
            glyphNames.append(newLineKey)
        for currentGlyphNumber, currentGlyphLine in enumerate(newLine.split(currentGlyphKey)):
            if currentGlyphNumber > 0:
                layerName = ""
                if currentGlyphLine.startswith(layerNameSplitter):
                    layerName, *_ = currentGlyphLine.split(" ")
                    currentGlyphLine = currentGlyphLine[len(layerName) + 1:]
                glyphNames.append(currentGlyphKey + layerName)
            for currentSelectionNumber, currentSelectionLine in enumerate(currentGlyphLine.split(currentSelectionKey)):
                if currentSelectionNumber > 0:
                    glyphNames.append(currentSelectionKey)
                line = currentSelectionLine
                compileStack = None
                unicodeStack = []
                bigUnicodeStack = ""
                for c in line:
                    if ord(c) in [0xD83D, 0xD83C]:
                        bigUnicodeStack += c
                        continue
                    c = bigUnicodeStack + c
                    bigUnicodeStack = ""
                    # start a glyph name compile.
                    if c == "/":
                        if unicodeStack:
                            mergeUnicodeStack(glyphNames, unicodeStack, cmap, allowShapingWithGlyphs, direction)
                        unicodeStack = []
                        # finishing a previous compile.
                        if compileStack is not None:
                            # only add the compile if something has been added to the stack.
                            if compileStack:
                                mergeCompileStack(glyphNames, compileStack, groups)
                        # reset the stack.
                        compileStack = []
                    # adding to or ending a glyph name compile.
                    elif compileStack is not None:
                        # space. conclude the glyph name compile.
                        if c == " ":
                            # only add the compile if something has been added to the stack.
                            if compileStack:
                                mergeCompileStack(glyphNames, compileStack, groups)
                            compileStack = None
                        # add the character to the stack.
                        else:
                            compileStack.append(c)
                    # adding a character that needs to be converted to a glyph name.
                    else:
                        if ord(c) not in cmap:
                            if unicodeStack:
                                mergeUnicodeStack(glyphNames, unicodeStack, cmap, allowShapingWithGlyphs, direction, fontData, fontObject)
                            glyphNames.append(c)
                            unicodeStack = []
                        else:
                            unicodeStack.append(c)
                if unicodeStack:
                    mergeUnicodeStack(glyphNames, unicodeStack, cmap, allowShapingWithGlyphs, direction, fontData, fontObject)
                unicodeStack = []

    # catch remaining compile.
    if compileStack:
        mergeCompileStack(glyphNames, compileStack, groups)
    if unicodeStack:
        mergeUnicodeStack(glyphNames, unicodeStack, cmap, allowShapingWithGlyphs, direction, fontData, fontObject)
    return glyphNames


def buildFontData(layer, useFeatures=True):
    glyphOrder = sorted(layer.keys() | set(["space", ".notdef", ".fallbackGlyph"]))

    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder(glyphOrder)
    fb.setupCharacterMap({uni: names[0] for uni, names in layer.unicodeData.items()})
    if useFeatures:
        fb.addOpenTypeFeatures(layer.font.features.text)
    fb.setupGlyf({glyphName: _dummyGlyph for glyphName in glyphOrder})
    fb.setupHorizontalMetrics({glyphName: (0, 0) for glyphName in glyphOrder})
    fb.setupHorizontalHeader(ascent=0, descent=0)
    data = io.BytesIO()
    fb.save(data)
    data = data.getvalue()
    data = AppKit.NSData.dataWithBytes_length_(data, len(data))
    return data, fb.font


# overwrite internals

def get(self):
    text = self.getRaw()
    glyphNames = []
    direction = self.getNSTextField().baseWritingDirection() == AppKit.NSWritingDirectionRightToLeft
    try:
        try:
            fontData, fontObject = buildFontData(self._layer)
        except Exception as e:
            print(f"Font build error: {e}")
            fontData, fontObject = buildFontData(self._layer, useFeatures=False)

        glyphNames = splitText(text, self._layer.unicodeData, self._font.groups, self._font.keys(), direction, fontData=fontData, fontObject=fontObject)
    except Exception as e:
        print(e)
    return glyphNames


import lib.UI.spaceCenter.glyphSequenceEditText
lib.UI.spaceCenter.glyphSequenceEditText.GlyphSequenceEditText.get = get
lib.UI.spaceCenter.glyphSequenceEditText.GlyphSequenceEditComboBox.get = get