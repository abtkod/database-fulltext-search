import config
import partition as pt
import enhancer.solutions as sol
from whoosh import index
import config, logging
import sys

LOGGER = logging.getLogger()


def partition_and_generate_distributions(index_name: str):
    configuration = config.get_paths()
    ix = index.open_dir(configuration[index_name], readonly=True)
    LOGGER.info('Index path: ' + configuration[index_name])
    with ix.reader() as ix_reader:
        pa = pt.Partitioner(ix, ix_reader)
        print('Partitioner initiated!')
        parts = pa.generate([0.98, 0.1])
        parts = [p for p in parts]
        print('Parts created!')
        print('naive1 ({}, {})'.format(parts[0].name, parts[1].name))
        sol.generate_distance_distributions(cache=parts[0], disk=parts[1],
                                            save_path='/data/khodadaa/index/data', distance_type=['kld', 'avg-kld'])


if __name__ == '__main__':
    config.setup_logger('_recursive_enhance')
    # save_dir = sys.argv[1]
    # cache_distribution_path = sys.argv[2]
    # disk_distribution_path = sys.argv[3]
    # config.setup_logger(file_name='_enhance')
    #
    # cache_ranges = [(0.0, 1.0)]
    # disk_ranges = [(0.0, 0.2), (0.0, 1.0)]
    #
    # for c in cache_ranges:
    #     for d in disk_ranges:
    #         sol.naive1(cache_distribution_path=cache_distribution_path, disk_distribution_path=disk_distribution_path,
    #                    save_log_path=save_dir, use_column_with_index=2, cache_start_range=c[0], cache_end_range=c[1],
    #                    disk_start_range=d[0], disk_end_range=d[1], equal_add_delete=True)
    #         # sol.naive2(cache_distribution_path=cache_distribution_path, disk_distribution_path=disk_distribution_path,
    #         #            save_log_path=save_dir, change_fraction=0.17, cache_start_range=c[0], cache_end_range=c[1],
    #         #            disk_start_range=d[0], disk_end_range=d[1], equal_add_delete=True)
    index_name = "wiki13_index"
    configuration = config.get_paths()
    ix = index.open_dir(configuration[index_name], readonly=True)
    LOGGER.info('Index path: ' + configuration[index_name])
    with ix.reader() as ix_reader:
        pa = pt.Partitioner(ix, ix_reader)
        LOGGER.info('Partitioner initiated!')
        parts = pa.generate([0.98, 0.0])
        parts = [p for p in parts]
        LOGGER.info('recursive ({}, {})'.format(parts[0].name, parts[1].name))
        sol.recursive_refine(cache=parts[0], disk=parts[1], save_log_path="/data/khodadaa/lucene-index/recursive")
