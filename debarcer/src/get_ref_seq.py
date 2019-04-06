
import pysam

def get_ref_seq(contig, region_start, region_end, config):
    """Gets reference sequence on a region from reference file."""
    print(contig,region_start,region_end,config)
    print(config['PATHS']['reference_file'])
    with pysam.FastaFile(config['PATHS']['reference_file']) as reader:
        ref_seq = reader.fetch(contig, region_start, region_end).upper()

    return ref_seq
