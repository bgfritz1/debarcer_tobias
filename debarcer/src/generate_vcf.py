
import sys
import pysam
import configparser
import argparse
import operator
import functools
from src.generate_consensus import ConsDataRow
from src.get_ref_seq import get_ref_seq

def parse_raw_table(cons_file, f_sizes):
    """Parses a .cons file generated by generate_consensus into VCF entries."""
    
    rows = {f_size: [] for f_size in f_sizes}
    
    with open(cons_file, "r") as reader:

        f_size = 0

        for line in reader:
            
            if line.startswith('#'):
                
                f_size = line.split('\t')[11]

            elif f_size in f_sizes:
                
                rows[f_size].append(line)
        rows.head()        
    return rows


def write_rows(cons_data, f_size, contig, region_start, region_end, output_path, config):

    with open("{}/{}:{}-{}.{}.vcf".format(output_path, contig, region_start, region_end, f_size), "w") as writer:

        writer.write("##fileformat=VCFv4.2\n")
        writer.write("##reference={}\n".format(config['PATHS']['reference_file']))
        writer.write("##source=Debarcer2\n")
        writer.write("##f_size={}\n".format(f_size))
        
        ## INFO/FILTER/FORMAT metadata
        writer.write("##INFO=<ID=RDP,Number=1,Type=Integer,Description=\"Raw Depth\">\n")
        writer.write("##INFO=<ID=CDP,Number=1,Type=Integer,Description=\"Consensus Depth\">\n")
        writer.write("##INFO=<ID=MIF,Number=1,Type=Integer,Description=\"Minimum Family Size\">\n")
        writer.write("##INFO=<ID=MNF,Number=1,Type=Float,Description=\"Mean Family Size\">\n")
        writer.write("##FILTER=<ID=a10,Description=\"Alt allele depth below 10\">\n")
        writer.write("##FORMAT=<ID=AD,Number=1,Type=Integer,Description=\"Allele Depth\">\n")
        writer.write("##FORMAT=<ID=AL,Number=R,Type=Integer,Description=\"Alternate Allele Depth\">\n")
        writer.write("##FORMAT=<ID=AF,Number=R,Type=Float,Description=\"Alternate Allele Frequency\">\n")
  
        writer.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n")
        
        for row in cons_data[f_size]:
            
            writer.write(row)


def vcf_output(cons_data, f_size, ref_seq, contig, region_start, region_end, output_path, config):
    """Writes a .vcf consensus file."""
    
    with open("{}/{}:{}-{}.fsize{}.vcf".format(output_path, contig, region_start, region_end, f_size), "w") as writer:
        
        writer.write("##fileformat=VCFv4.2\n")
        writer.write("##reference={}\n".format(config['PATHS']['reference_file']))
        writer.write("##source=Debarcer2\n")
        writer.write("##f_size={}\n".format(f_size))
        
        ## INFO/FILTER/FORMAT metadata
        writer.write("##INFO=<ID=RDP,Number=1,Type=Integer,Description=\"Raw Depth\">\n")
        writer.write("##INFO=<ID=CDP,Number=1,Type=Integer,Description=\"Consensus Depth\">\n")
        writer.write("##INFO=<ID=MIF,Number=1,Type=Integer,Description=\"Minimum Family Size\">\n")
        writer.write("##INFO=<ID=MNF,Number=1,Type=Float,Description=\"Mean Family Size\">\n")
        writer.write("##FILTER=<ID=a10,Description=\"Alt allele depth below 10\">\n")
        writer.write("##FORMAT=<ID=AD,Number=1,Type=Integer,Description=\"Allele Depth\">\n")
        writer.write("##FORMAT=<ID=AL,Number=R,Type=Integer,Description=\"Alternate Allele Depth\">\n")
        writer.write("##FORMAT=<ID=AF,Number=R,Type=Float,Description=\"Alternate Allele Frequency\">\n")
        
        ref_threshold = float(config['REPORT']['percent_ref_threshold']) if config else 95.0
        all_threshold = float(config['REPORT']['percent_allele_threshold']) if config else 2.0
        
        writer.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE\n")

        for base_pos in range(region_start, region_end):
            if base_pos in cons_data[f_size]:
                
                row = cons_data[f_size][base_pos]
                ref = row.get_ref_info()
                cons = row.get_cons_info()
                stats = row.get_stats()

                if stats['ref_freq'] <= ref_threshold:
                        
                    alleles = row.get_alleles(all_threshold)
                    ref_bases = set([allele[0] for allele in alleles])
                    ref_allele = (ref_seq[base_pos - region_start], ref_seq[base_pos - region_start])
                    depths = row.impute_allele_depths()
                    ref_depth = depths[ref_allele] if ref_allele in depths else 0
                    alt_freqs = row.impute_allele_freqs(all_threshold)

                    info = "RDP={};CDP={};MIF={};MNF={:.1f}".format(
                        stats['rawdp'], stats['consdp'], stats['min_fam'], stats['mean_fam'])
                    fmt_string = "AD:AL:AF" # Allele depth, alt allele depth, reference frequency

                    for ref_base in ref_bases:
                        snips = []
                        for allele in alleles:
                            if allele[0] == ref_base:
                                snips.append(allele)

                        alt_string = ','.join( [allele[1] for allele in snips] )
                        depth_string = ','.join( [str(depths[allele]) for allele in snips] )
                        freq_string = ','.join( ["{:.2f}".format(alt_freqs[allele]) for allele in snips] )
                        smp_string = "{}:{}:{}".format(ref_depth, depth_string, freq_string)
                        filt = "PASS" if any( [depths[alt] > 10 for alt in snips] ) else "a10"

                        writer.write("{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\t{}\n".format(
                            contig, base_pos, ".", ref_base, alt_string, "0", filt, info, fmt_string, smp_string))


def generate_vcf_output(cons_file, f_sizes, contig, region_start, region_end, output_path, config):
    """(Main) generates VCF output file(s)."""

    ## Get reference sequence for the region 
    ref_seq = get_ref_seq(contig, region_start, region_end, config)
    

    ## Parse table to extract VCF events
    cons_data = parse_raw_table(cons_file, f_sizes)
    

    ## Generate vcf files
    for f_size in f_sizes:
        if f_size in cons_data:
            write_rows(cons_data, f_size, contig, region_start, region_end, output_path, config)


if __name__=="__main__":
    ## Argument + config parsing and error handling
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--cons_file', help='Path to your cons_file.')
    parser.add_argument('-f', '--f_sizes', help='Comma-separated list of f_sizes to make VCF files for.')
    parser.add_argument('-r', '--region', help='Region to analyze (string of the form chrX:posA-posB).')
    parser.add_argument('-o', '--output_path', help='Path to write output files to.')
    parser.add_argument('-c', '--config', help='Path to your config file.')

    args = parser.parse_args()

    if args.config:
        config = configparser.ConfigParser()
        config.read(args.config)
    else:
        config = None
    
    cons_file = args.cons_file

    f_sizes = args.f_sizes.split(',')

    region = args.region
    if any(x not in region for x in ["chr", ":", "-"]):
        raise ValueError('Incorrect region string (should look like chr1:1200000-1250000).')
    sys.exit(1)

    contig = region.split(":")[0]
    region_start = int(region.split(":")[1].split("-")[0])
    region_end = int(region.split(":")[1].split("-")[1])

    output_path = handle_arg(args.output_path, config['PATHS']['output_path'] if config else None, 
                    'No output path provided in args or config.')

    ## Output
    generate_vcf_output(cons_file, f_sizes, contig, region_start, region_end, output_path, config)
