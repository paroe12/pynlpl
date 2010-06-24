#---------------------------------------------------------------
# PyNLPl - Simple Read library for D-Coi/SoNaR format
#   by Maarten van Gompel, ILK, Universiteit van Tilburg
#   http://ilk.uvt.nl/~mvgompel
#   proycon AT anaproy DOT nl
#
#   Licensed under GPLv3
#
# This library facilitates parsing and reading corpora in
# the SoNaR/D-Coi format.
#
#----------------------------------------------------------------


import codecs
import re
import glob
import os.path

try:
    from lxml import etree as ElementTree #try lxml
except ImportError:
    from xml.etree.ElementTree import ElementTree #fall back to ElementTree

from StringIO import StringIO
from time import time

namespaces = {
    'dcoi': "http://lands.let.ru.nl/projects/d-coi/ns/1.0",
    'standalone':"http://ilk.uvt.nl/dutchsemcor-standalone",
    'dsc':"http://ilk.uvt.nl/dutchsemcor",
    'xml':"http://www.w3.org/XML/1998/namespace"
}

class CorpusDocument:
    """This class represent one document/text of the Corpus"""

    def __init__(self, filename, encoding = 'iso-8859-15'):
        self.filename = filename
        self.id = os.path.basename(filename).split(".")[0]
        self.f = codecs.open(filename,'r', encoding)

    def __iter__(self):
        """Iterate over all words, a four-tuple (word,id,pos,lemma), in the document"""
        r = re.compile('<w.*xml:id="([^"]*)"(.*)>(.*)</w>')
        for line in self.f.readlines():
            matches = r.findall(line)
            for id, attribs, word in matches:
                pos = lemma = None
                m = re.findall('pos="([^"]+)"', attribs)
                if m: pos = m[0]

                m = re.findall('lemma="([^"]+)"', attribs)
                if m: lemma = m[0]
        
                yield word, id, pos, lemma       
    
    def words(self):
        #alias
        return iter(self) 


    def sentences(self):
        """Iterate over all sentences (sentence_id, sentence) in the document, sentence is a list of 4-tuples (word,id,pos,lemma)"""
        prevp = 0
        prevs = 0
        prevw = 0
        sentence = [];
        sentence_id = ""
        for word, id, pos, lemma in iter(self):
            doc_id, ptype, p, s, w = re.findall('([\w\d-]+)\.(p|head)\.(\d+)\.s\.(\d+)\.w\.(\d+)',id)[0]
            if ((p != prevp) or (s != prevs)) and sentence:
                yield sentence_id, sentence
                sentence = []
                sentence_id = doc_id + '.' + ptype + '.' + str(p) + '.s.' + str(s)
            sentence.append( (word,id,pos,lemma) )     
            prevp = p
            prevs = s
            prevw = w
        if sentence:
            yield sentence_id, sentence 
            
    def paragraphs(self, with_id = False):
        """Extracts paragraphs, returns list of plain-text(!) paragraphs"""
        prevp = 0
        partext = []
        for word, id, pos, lemma in iter(self):
            doc_id, ptype, p, s, w = re.findall('([\w\d-]+)\.(p|head)\.(\d+)\.s\.(\d+)\.w\.(\d+)',id)[0]
            if prevp != p and partext:
                    yield ( doc_id + "." + ptype + "." + prevp , " ".join(partext) )
                    partext = []
            partext.append(word)
            prevp = p   
        if partext:
            yield (doc_id + "." + ptype + "." + prevp, " ".join(partext) )
                
class Corpus:
    def __init__(self,corpusdir, extension = 'pos', restrict_to_collection = ""):
        self.corpusdir = corpusdir
        self.extension = extension
        self.restrict_to_collection = restrict_to_collection

    def __iter__(self):
        for d in glob.glob(self.corpusdir+"/*"):
            if (not self.restrict_to_collection or self.restrict_to_collection == d) and (os.path.isdir(d)):
                for f in glob.glob(d+ "/*." + self.extension):
                    yield CorpusDocument(f)

#######################################################

def ns(namespace):
    """Resolves the namespace identifier to a full URL""" 
    global namespaces
    return '{'+namespaces[namespace]+'}'


class CorpusX(Corpus):
    def __iter__(self):
        for d in glob.glob(self.corpusdir+"/*"):
            if (not self.restrict_to_collection or self.restrict_to_collection == d) and (os.path.isdir(d)):
                for f in glob.glob(d+ "/*." + self.extension):
                    yield CorpusDocumentX(f)


class CorpusDocumentX:
    """This class represent one document/text of the Corpus, loaded into memory at once and retaining the full structure"""

    def __init__(self, filename, tree = None, index=True ):
        global namespaces
        self.filename = filename
        if not tree:
            self.tree = ElementTree.parse(self.filename)
            self.committed = True
        elif isinstance(tree, ElementTree._Element):
            self.tree = tree
            self.committed = False

        #Grab root element and determine if we run inline or standalone
        self.root =  self.xpath("/dcoi:DCOI")
        if self.root:
	    self.root = self.root[0] 
            self.inline = True
        else:
            raise Exception("Not in DCOI/SoNaR format!")
            #self.root = self.xpath("/standalone:text")
            #self.inline = False
            #if not self.root:
            #    raise FormatError()            

        #build an index
        self.index = {}
        if index:
            self._index(self.root)

    def _index(self,node):
        if ns('xml') + 'id' in node.attrib:
                self.index[node.attrib[ns('xml') + 'id']] = node
        for subnode in node: #TODO: can we do this with xpath instead?
            self._index(subnode)

    def validate(self, formats_dir="../formats/"):
        """checks if the document is valid"""
        #TODO: download XSD from web
        if self.inline:
            xmlschema = ElementTree.XMLSchema(ElementTree.parse(StringIO("\n".join(open(formats_dir+"dcoi-dsc.xsd").readlines()))))
            xmlschema.assertValid(self.tree)
            #return xmlschema.validate(self)
        else:
            xmlschema = ElementTree.XMLSchema(ElementTree.parse(StringIO("\n".join(open(formats_dir+"dutchsemcor-standalone.xsd").readlines()))))
            xmlschema.assertValid(self.tree)
            #return xmlschema.validate(self)

    def xpath(self, expression):
        """Executes an xpath expression using the correct namespaces"""
        global namespaces
        return self.tree.xpath(expression, namespaces=namespaces)


    def __exists__(self, id):
        return (id in self.index)

    def __getitem__(self, id):
        return self.index[id]


    def paragraphs(self, node=None):
        """iterate over paragraphs"""
        if node == None: node = self
        return node.xpath("//dcoi:p")

    def sentences(self, node=None):
        """iterate over sentences"""
        if node == None: node = self
        return node.xpath("//dcoi:s")

    def words(self,node=None):
        """iterate over words"""
        if node == None: node = self
        return node.xpath("//dcoi:w")

    def save(self, filename=None):
        if not filename: filename = self.filename
        self.tree.write(filename) #, 'iso-8859-15', True)

