#! /usr/bin/env python
# -*- coding: utf8 -*-


###############################################################
#  PyNLPl - FreeLing Library
#       by Maarten van Gompel (proycon)
#       http://ilk.uvt.nl/~mvgompel
#       Radboud University Nijmegen
#       
#       Licensed under GPLv3
# 
# Generic Tagger interface for PoS-tagging and lemmatisation,
# offers an interface to various software
#
###############################################################


import sys
import codecs
import json
import getopt
import locale

    
class Tagger(object):    
     def __init__(self, *args):        
        global WSDDIR
        self.tagger = None
        if args[0] == "file":
            if len(args) != 3:
                raise Exception("Syntax: frog:[filename]")
            self.tagger = codecs.open(args[1],'r','utf-8') 
        elif args[0] == "frog":
            if len(args) != 3:
                raise Exception("Syntax: frog:[host]:[port]")
            from pynlpl.clients.frogclient import FrogClient
            self.mode = "frog"
            port = int(args[2])
            self.tagger = FrogClient(args[1],port)                
        elif args[0] == "freeling":
            if len(args) != 3:
                raise Exception("Syntax: freeling:[host]:[port]")
            from pynlpl.clients.freeling import FreeLingClient
            self.mode = "freeling"
            host = args[1]
            port = int(args[2])
            self.tagger = FreeLingClient(host,port)            
        elif args[0] == "corenlp":
            if len(args) != 1:
                raise Exception("Syntax: corenlp")
            import corenlp
            self.mode = "corenlp"
            print >>sys.stderr, "Initialising Stanford Core NLP"
            self.tagger = corenlp.StanfordCoreNLP()                        
        elif args[0] == "durmlex":
            if not len(args) == 2:
                raise Exception("Syntax: durmlex:[filename]")
            print >>sys.stderr, "Reading durm lexicon: ", args[1]
            self.mode = "lookup"
            self.tagger = {}
            f = codecs.open(args[1],'r','utf-8')
            for line in f:
                fields = line.split('\t')
                wordform = fields[0].lower()
                lemma = fields[4].split('.')[0]
                self.tagger[wordform] = (lemma, 'n')
            f.close()
            print >>sys.stderr, "Loaded ", len(self.tagger), " wordforms"
        elif args[0] == "oldlex":
            if not len(args) == 2:
                raise Exception("Syntax: oldlex:[filename]")
            print >>sys.stderr, "Reading OLDLexique: ", args[1]
            self.mode = "lookup"
            self.tagger = {}
            f = codecs.open(args[1],'r','utf-8')
            for line in f:
                fields = line.split('\t')
                wordform = fields[0].lower()                
                lemma = fields[1]
                if lemma == '=': 
                    lemma == fields[0]
                pos = fields[2][0].lower()
                self.tagger[wordform] = (lemma, pos)
                print >>sys.stderr, "Loaded ", len(self.tagger), " wordforms"
            f.close()
        else:
            raise Exception("Invalid mode: " + args[0])
        
     def __iter__(self):
        if self.mode != 'file':
            raise Exception("Iteration only possible in file mode")
        line = self.tagger.next()
        newwords = []
        postags = []
        lemmas = []    
        for item in line:            
            word,lemma,pos = item.split('|')
            newwords.append(word)
            postags.append(pos)
            lemmas.append(lemma)
        yield newwords, postags, lemmas        
        
     def process(self, words, debug):
        if self.mode == 'file':
            line = self.tagger.next()
            newwords = []
            postags = []
            lemmas = []    
            for item in line:            
                word,lemma,pos = item.split('|')
                newwords.append(word)
                postags.append(pos)
                lemmas.append(lemma)
            return newwords, postags, lemmas
        elif self.mode == "frog":
            newwords = []
            postags = []
            lemmas = []             
            for fields in self.tagger.process(' '.join(words)):
                word,lemma,morph,pos = fields[:4]
                newwords.append(word)
                postags.append(pos)
                lemmas.append(lemma)
            return newwords, postags, lemmas                
        elif self.mode == "freeling":
            postags = []
            lemmas = []
            for fields in self.tagger.process(words, debug):
                word, lemma,pos = fields[:3]
                postags.append(pos)
                lemmas.append(lemma)
            return words, postags, lemmas            
        elif self.mode == "corenlp":            
            data = json.loads(self.tagger.parse(" ".join(words)))
            words = []
            postags = []
            lemmas = []
            for sentence in data['sentences']:
                for word, worddata in sentence['words']:
                    words.append(word)
                    lemmas.append(worddata['Lemma'])
                    postags.append(worddata['PartOfSpeech'])
            return words, postags, lemmas
        elif self.mode == 'tablelookup':
            postags = []
            lemmas = []
            for word in words:
                try:
                    lemma, pos = self.tagger[word.lower()]
                except KeyError: 
                    lemmas.append(word)
                    pos.append('?')
            return words, pos, lemmas
    
     def tag(self, f_in, f_out,oneperline=False, debug=False):
        linenum = 0
        for line in f_in:
            linenum += 1
            print >>sys.stderr, " Tagger input @" + str(linenum)
            if line.strip():
                words = line.strip().split(' ')
                words, postags, lemmas = self.process(words, debug)
                out = u""
                for word, pos, lemma in zip(words,postags, lemmas):
                   if word is None: word = ""
                   if lemma is None: lemma = "?"
                   if pos is None: pos = "?"                    
                   if oneperline:
                        if out: out += "\n"
                        out += word + "\t" + lemma + "\t" + pos
                   else: 
                        if out: out += " "
                        if '|' in word:
                            word = word.replace('|','_')
                        if '|' in lemma:
                            lemma = lemma.replace('|','_') 
                        if '|' in pos:
                            pos = pos.replace('|','_') 
                        out += word + "|" + lemma + "|" + pos
                if not isinstance(out, unicode):
                    out = unicode(out, 'utf-8')
                f_out.write(out)
                if oneperline:
                    f_out.write("\n\n")
            else:
                f_out.write("\n")

def usage():
    print >>sys.stderr, "tagger.py -c [conf] -f [input-filename] -o [output-filename]" 

if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:c:")
    except getopt.GetoptError, err:
        # print help information and exit:
        print str(err)
        usage()
        sys.exit(2)   
    
    taggerconf = None
    filename = None
    outfilename = None        
    oneperline = False
    debug = False
        
    for o, a in opts:
        if o == "-c":	
            taggerconf = a
        elif o == "-f":	
            filename = a
        elif o == '-o':
            outfilename =a
        elif o == '-l':
            oneperline = True
        elif o == '-D':
            debug = True
        else: 
            print >>sys.stderr,"Unknown option: ", o
            sys.exit(2)
    

    if not taggerconf:
        print >>sys.stderr, "ERROR: Specify a tagger configuration with -c"
        sys.exit(2)
    if not filename:
        print >>sys.stderr, "ERROR: Specify a filename with -f"
        sys.exit(2)
    
        
    if outfilename: 
        f_out = codecs.open(outfilename,'w','utf-8')
    else:
        f_out = codecs.getwriter(locale.getpreferredencoding())(sys.stdout);
        
    f_in = codecs.open(filename,'r','utf-8')
    
    tagger = Tagger(*taggerconf.split(':'))
    tagger.tag(f_in, f_out, oneperline, debug)
    
    f_in.close()
    if outfilename:
        f_out.close()
    
      
            
        