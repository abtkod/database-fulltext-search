import whoosh.index as index
from whoosh import sorting
from whoosh.qparser import QueryParser, MultifieldParser, GtLtPlugin
from collections import defaultdict
import config
import metrics
from math import log
import operator


# A filter over Index
class IndexPartition(object):

    def __init__(self, file_index: index.FileIndex, index_docnums: list, name: str):
        self.name = name
        self.ix = file_index
        self.docnums = set(index_docnums)
        self._tfs = self._get_terms('body')

    def doc_count(self):
        return len(self.docnums)

    def _get_terms(self, fieldname='body'):
        with self.ix.reader() as ireader:
            if not ireader.has_vector(list(self.docnums)[0], fieldname):
                raise NotImplementedError('Forward index (vector) is not available for {}'.format(fieldname))

            tfs = defaultdict(int)
            for dn in list(self.docnums):
                tfs_list = ireader.vector_as('frequency', dn, fieldname)
                for tf in tfs_list:
                    tfs[tf[0]] += tf[1]
        return tfs

    def all_terms_count(self):
        count = 0
        for t, f in self._tfs:
            count += f
        return count

    def add_doc(self, docnum, fieldname='body'):
        if docnum not in self.docnums:
            self.docnums.add(docnum)
            with self.ix.reader() as ireader:
                if not ireader.has_vector(docnum, fieldname):
                    raise NotImplementedError('Forward index (vector) is not available for {}'.format(fieldname))

                tfs_list = ireader.vector_as('frequency', docnum, fieldname)
                for tf in tfs_list:
                    self._tfs[tf[0]] += tf[1]

    def search(self, text: str, sorted_by_count=False, fieldname='body'):
        with self.ix.searcher() as isearcher:
            skw = {'limited': None}
            skw['q'] = QueryParser("body", self.ix.schema).parse(text)
            if sorted_by_count:
                skw['sortedby'] = sorting.FieldFacet('count', reverse=True)
            results = isearcher.search(**skw)
        return results.docs(), results.items()

    def get_tfs(self):
        return self._tfs.copy()

    def get_dfs(self):
        dfs = defaultdict(int)
        for t in self._tfs.keys():
            docnums, _ = self.search(t)
            dfs[t] = len(docnums.intersection(self.docnums))
        return dfs


    def get_tfidfs(self, fieldname='body'):
        tfidfs = defaultdict(float)
        dfs = self.get_dfs()
        with self.ix.reader() as ireader:
            for t in ireader.field_terms(fieldname):
                # divide by dfs[t] as of normalization
                tfidfs[t] = (self._tfs[t]/dfs[t]) * log(ireader.doc_count() / ireader.doc_frequency(fieldname, t))
        return tfidfs

    def get_docnums(self):
        return list(self.docnums)

    def remove_doc(self, docnum, fieldname='body'):
        if docnum in self.docnums:
            self.docnums.remove(docnum)
            with self.ix.reader() as ireader:
                if not ireader.has_vector(docnum, fieldname):
                    raise NotImplementedError('Forward index (vector) is not available for {}'.format(fieldname))

                tfs_list = ireader.vector_as('frequency', docnum, fieldname)
                for tf in tfs_list:
                    self._tfs[tf[0]] -= tf[1]
                    if self._tfs[tf[0]] <= 0:
                        if self._tfs[tf[0]] == 0:
                            self._tfs.pop(tf[0])
                        else:
                            raise ValueError('Negative value for tf in partition {}'.format(self.name))

    def all_stored_fields(self):
        with self.ix.reader() as ireader:
            for dn in list(self.docnums):
                yield ireader.stored_fields(dn)

    def _all_stored_fields(self):
        sf = {}
        with self.ix.reader() as ireader:
            for dn in list(self.docnums):
                sf[dn] = ireader.stored_fields(dn)
        return sf

    def get_popularity_distribution(self)-> list:
        pop_dist = defaultdict(int)
        with self.ix.reader() as ireader:
            for dn in list(self.docnums):
                pop_dist[dn] = ireader.stored_fields(dn)['count']
        return sorted(pop_dist.items(), key=operator.itemgetter(1), reverse=True)

    def doc_kld(self, docnum, fieldname='body'):
        with self.ix.reader() as ireader:
            if not ireader.has_vector(docnum, fieldname):
                raise NotImplementedError('Forward index (vector) is not available for doc {} field {}'
                                          .format(docnum, fieldname))

            doc_tfs = ireader.vector_as('frequency', docnum, fieldname)
        return distance(self.get_tfs(), doc_tfs, metrics.kl_divergence)

    def doc_avg_kld(self, docnum, fieldname='body'):
        with self.ix.reader() as ireader:
            if not ireader.has_vector(docnum, fieldname):
                raise NotImplementedError('Forward index (vector) is not available for doc {} field {}'
                                          .format(docnum, fieldname))

            doc_tfs = ireader.vector_as('frequency', docnum, fieldname)
            ireader.stored_fields()
        raise NotImplementedError



def distance(part1: defaultdict, part2: defaultdict, metric: function) -> float:
    return metric(part1, part2)


def kl_divergence(part1: IndexPartition, part2: IndexPartition):
    return distance(part1.get_tfs(), part2.get_tfs(), metrics.kl_divergence)


def avg_kl_divergence(part1: IndexPartition, part2: IndexPartition):
    return distance(part1.get_tfidfs(), part2.get_tfidfs(), metrics.avg_kl_divergence)


def combine(part1: IndexPartition, part2: IndexPartition):
    com_part = IndexPartition(part1.ix, part1.get_docnums())
    for dn in part2.get_docnums():
        com_part.add_doc(dn)
    return com_part

def partition_popularity(index_path, threasholds=[0.9]):
    threasholds = list(set(threasholds))
    threasholds.sort(reverse=True)
    ix = index.open_dir(index_path, readonly=True)
    with ix.searcher() as isearcher:
        isearcher.documents()

class Partitioner(object):

    def __init__(self, index_path: str):
        self._ix = index.open_dir(index_path, readonly=True)
        self._docnum_pop = self._docnum_pop()

    def _docnum_pop(self):
        ireader = self._ix.reader()
        dn_pop = defaultdict(int)
        for dx in ireader.iter_docs():
            dn_pop[dx[0]] = int(dx[1]['count'])
        return dn_pop

    def get_sorted_ids(self):
        return sorted(self._docnum_pop().items(), key=operator.itemgetter(1), reverse=True)



# def partition_popularity_based(index_path, low_pop_ratio, high_pop_ratio=1.0):
#     ix = index.open_dir(index_path, readonly=True)
#     facet = sorting.FieldFacet('count', reverse=True)
#
#     with ix.reader() as reader:
#         tot_docs_count = ix.doc_count()
#         cache_docs_count = int(topFraction * tot_docs_count)
#         id_list = get_sorted_ids(reader)
#         cache_id_list = id_list[:cache_docs_count]
#         db_id_list = id_list[cache_docs_count:]
#         print(reader.doc_field_length(5266, 'body'))
#         # v = reader.vector(5266, 'body')
#         # print(v)
#
#
#
#         # print(reader.frequency('body', ''))
#         # terms = reader.field_terms('body')
#     with ix.searcher() as searcher:
#         qp = MultifieldParser(['body', 'count'], schema=ix.schema)
#         qp.add_plugin(GtLtPlugin())
#         query = qp.parse('Iran')
#         results = searcher.search(query, sortedby=facet, limit=None)
#
#         for res in results:
#             print(res)


if __name__ == '__main__':
    configuration = config.get()
    # partition_popularity_based(configuration['wiki13_index'])
    ix = index.open_dir(configuration['wiki13_index'])
    cache_partition = IndexPartition(ix, [0, 1], 'cache')
    db_partition = IndexPartition(ix, [2, 3], 'db')
    print(cache_partition._tfs)
    print(db_partition._tfs)
    cache_partition.remove_doc(1)
    db_partition.add_doc(1)
    print(cache_partition._tfs)
    print(db_partition._tfs)
    print(db_partition._all_stored_fields())