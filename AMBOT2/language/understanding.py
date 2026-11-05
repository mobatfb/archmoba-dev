"""Pronombres dependientes del hablante y nombres aprendidos en contexto."""
import json
import re
import unicodedata
from pathlib import Path


def normalize(text):
    return "".join(
        c for c in unicodedata.normalize("NFD",str(text).lower().strip())
        if unicodedata.category(c)!="Mn"
    )


class Pronouns:
    """Roles conversacionales; no confundir 'yo' con un robot fijo."""
    def resolve(self,word,speaker="maestro",listener="ambot"):
        word=normalize(word)
        if word=="yo":
            return [speaker]
        if word=="tu":
            return [listener]
        if word in ("nosotros","nosotras"):
            return sorted({speaker,listener})
        if word in ("vosotros","vosotras","ustedes"):
            # Solo hay dos interlocutores en AMBOT2. El plural dirigido
            # conserva el rol aunque haya un unico destinatario presente.
            return [listener]
        if word in ("el","ella"):
            return ["tercero_no_especificado"]
        if word in ("ellos","ellas"):
            return ["terceros_no_especificados"]
        return []


class LanguageMind:
    def __init__(self,path):
        self.path=Path(path)
        self.pronouns=Pronouns()
        self.labels={}   # id objeto -> palabra suministrada por maestro
        self.words={}    # palabra -> lista IDs observados
        self.questions=[]
        self.dialogues=0
        self._load()

    def _load(self):
        try:
            d=json.loads(self.path.read_text(encoding="utf-8"))
            self.labels={str(k):str(v) for k,v in d.get("labels",{}).items()}
            self.words={str(k):list(v) for k,v in d.get("words",{}).items()}
            self.questions=list(d.get("questions",[]))[-60:]
            self.dialogues=int(d.get("dialogues",0))
        except (OSError,ValueError,TypeError,AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "labels":self.labels,"words":self.words,
            "questions":self.questions[-60:],
            "dialogues":self.dialogues
        },ensure_ascii=False,indent=2),encoding="utf-8")
        temp.replace(self.path)

    def ask(self,text):
        self.questions.append(text)
        self.save()
        return text

    def associate(self,word,object_id):
        word=normalize(word)
        if not re.fullmatch(r"[a-zñ][a-zñ0-9 _-]{0,50}",word):
            raise ValueError("Palabra no valida")
        self.labels[str(object_id)]=word
        self.words.setdefault(word,[])
        if object_id not in self.words[word]:
            self.words[word].append(str(object_id))
        self.save()
        return "Veo este objeto y escuche '"+word+"'. ¿Es correcto?"

    def hear(self,text,selected=None,speaker="maestro",listener="ambot"):
        """Dialogo explicable, sin afirmar comprension semantica universal."""
        raw=str(text).strip()
        simple=normalize(raw.strip(" ¿?¡!.,:;"))
        if not simple:
            return ""
        self.dialogues+=1
        self.save()
        match=re.fullmatch(r"(?:esto es|se llama|este objeto es) (?:un |una |el |la )?(.+)",simple)
        if match:
            if selected is None:
                return self.ask("¿A cual objeto te refieres? Seleccionalo primero.")
            return self.associate(match.group(1),selected)
        if simple in ("que es esto","como se llama esto","como se llama","esto que es"):
            if not selected:
                return self.ask("¿A que objeto te refieres? Senalalo en el editor.")
            return (f"Me ensenaste que se llama '{self.labels[selected]}'."
                    if selected in self.labels else
                    self.ask("Todavia no se como se llama. ¿Me lo ensenas?"))
        m=re.search(r"\b(yo|tu|nosotros|nosotras|vosotros|vosotras|ustedes|el|ella|ellos|ellas)\b",simple)
        if m:
            referents=self.pronouns.resolve(m.group(1),speaker,listener)
            if simple.startswith(("quien soy","quien eres","quienes somos","quienes sois")):
                return "En esta conversacion '"+m.group(1)+"' se refiere a: "+", ".join(referents)+"."
            return ("Escuche '"+m.group(1)+"'. Aqui se refiere a: "
                    +", ".join(referents)+". ¿Que quieres que haga?")
        for word,items in self.words.items():
            if re.search(r"\b"+re.escape(word)+r"\b",simple):
                return "Relaciono '"+word+"' con "+str(len(items))+" objeto(s). ¿Que accion me ensenas?"
        return self.ask("Aun no comprendo '"+raw[:65]+"'. ¿Puedes mostrarme que significa?")
