from whoosh.index import create_in
from whoosh.fields import *
from traverse import access
from codecs import open
import config
import sys

schema = Schema(title=TEXT(stored=True), id=ID(stored=True), content=TEXT, popularity=NUMERIC(stored=True))


def build_index_wiki13(dir_path: str, save_path: str):
    wiki13_title_count = config.init()
    ix = create_in(save_path, schema)
    writer = ix.writer()
    docs = access(dir_path)
    fc = 0
    for dname, dpath in docs:
        fc +=1
        if fc%1000 == 0:
            print(fc, dpath)
        did = config.get_article_id_from_file_name(dname)
        if did not in wiki13_title_count:
            continue
        with open(dpath, 'r', encoding='utf-8') as fo:
            dcont = fo.read()
        writer.add_document(title= wiki13_title_count[did]['title'], id=did, content=dcont, popularity=wiki13_title_count[did]['count'])
        if fc > 200000:
            break
    writer.commit()
    return


if __name__ == '__main__':
    c = config.get()

    if len(sys.argv) > 3:
        build_index_wiki13(sys.argv[1], sys.argv[2])
    else:
        build_index_wiki13(c['wiki13_dir'], c['wiki13_index'])
