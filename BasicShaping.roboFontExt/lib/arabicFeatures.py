from fontTools.feaLib.parser import Parser
from fontTools.feaLib.ast import *
from ufo2ft.featureWriters.ast import getScriptLanguageSystems, findFeatureTags

SUFFIX_FEA_MAP = {  # suffix: feature_tag
                'init': 'init',
                'medi': 'medi',
                'fina': 'fina',
                }

def _getDefaultFeaFile():
    feaFileAst = FeatureFile()
    lang = LanguageSystemStatement("DFLT", "dftl")
    feaFileAst.statements.append(lang)
    return feaFileAst

def _getFeatureFileAST(font):
    featurefile = UnicodeIO(font.features.text)
    featurefile.name = font.path
    parser = Parser(featurefile, font.keys())
    return parser.parse()

def getAstIndexMap(feaFile):
    """
    Returns a dict in which the keys are feaLib.ast class and value is a list of
    indices which represents where is the object in feature file statements
    list.
    """
    indexMap = {}
    for i, statement in enumerate(feaFile.statements):
        indexMap.setdefault(type(statement), set()).add(i)
    return indexMap

def getFeatures(font):
    feaFileAst = _getDefaultFeaFile()
    if font.features.text is not None and font.features.text.strip():
        try:
            feaFileAst = _getFeatureFileAST(font)
        except FeatureLibError as e:
            print(e)
    langSysMap = getScriptLanguageSystems(feaFileAst)
    astIndexMap = getAstIndexMap(feaFileAst)
    if "Arab" not in langSysMap:
        arabLang = LanguageSystemStatement("Arab", "dftl")
        index = max(astIndexMap.get(LanguageSystemStatement, 0)) + 1
        feaFileAst.statements.insert(index, arabLang)
    feaTags = findFeatureTags(feaFileAst)
    if set(SUFFIX_FEA_MAP.values()) - feaTags == set():
        # features already exist
        return feaFileAst
    feaIndex = max(astIndexMap.get(FeatureBlock, [len(feaFileAst.statements)])) + 1
    glyphSet = sorted(font.keys())
    for suffix, tag in SUFFIX_FEA_MAP.items():
        fea = FeatureBlock(tag)
        fea.statements.append(ScriptStatement("arab"))
        suffix = f".{suffix}"
        lenSuffix = len(suffix)
        sourceList = [g for g in glyphSet if g.endswith(suffix) and g[:-lenSuffix] in glyphSet]
        targetList = [g[:-lenSuffix] for g in sourceList]
        source = GlyphClass(targetList)
        target = GlyphClass(sourceList)
        sub = SingleSubstStatement([source], [target], [], [], False)
        fea.statements.append(sub)
        feaFileAst.statements.insert(feaIndex, fea)
    return feaFileAst

if __name__ == '__main__':
    f = CurrentFont()
    print(getFeatures(f))
