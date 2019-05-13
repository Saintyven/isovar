# Copyright (c) 2016-2019. Mount Sinai School of Medicine
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""
IsovarResult is a collection of all information gathered about a variant
and any protein sequences which were successfully translated for it.
"""

from __future__ import print_function, division, absolute_import

import operator
from collections import OrderedDict

from .common import safediv
from .value_object import  ValueObject


class IsovarResult(ValueObject):
    """
    This object represents all information gathered about a variant,
    which includes the AlleleReads supporting any allele at this variant's
    locus and any protein sequences generated from an alt-allele cDNA
    assembly.
    """
    __slots__ = [
        "variant",
        "predicted_effect",
        "read_evidence",
        "sorted_protein_sequences",
        "filter_values_dict",
    ]

    def __init__(
            self,
            variant,
            predicted_effect,
            read_evidence,
            sorted_protein_sequences=None,
            filter_values_dict=None):
        self.variant = variant
        self.predicted_effect = predicted_effect
        self.read_evidence = read_evidence

        if sorted_protein_sequences is None:
            self.sorted_protein_sequences = []
        else:
            self.sorted_protein_sequences = sorted_protein_sequences

        if filter_values_dict is None:
            self.filter_values_dict = OrderedDict()
        else:
            self.filter_values_dict = filter_values_dict

    def apply_filters(self, filter_thresholds):
        """
        Creates a dictionary whose keys are named of different
        filter conditions and values are booleans, where True
        indicates whether this set of coverage stats passes
        the filter and False indicates that it failed.

        Parameters
        ----------
        filter_thresholds : dict or OrderedDict
            Every argument is supposed to be something like "max_alt_reads"
            where the first three characters are "min" or "max" and the
            rest of the name is either a field of IsovarResult or
            a numeric field like "num_alt_reads". The name of each filter
            maps to a cutoff value. Filters starting with "max"
            require that the corresponding field on CoverageStats
            is <= cutoff, whereas filters starting with
            "min" require >= cutoff.

        Returns
        -------
        Dictionary of filter names mapped to boolean value indicating
        whether this locus passed the filter.
        """
        filter_values_dict = OrderedDict()
        for name, threshold in filter_thresholds.items():
            parts = name.split("_")
            min_or_max = parts[0]
            field_name = "_".join(parts[1:])
            if min_or_max == "min":
                comparison_fn = operator.ge
            elif min_or_max == "max":
                comparison_fn = operator.le
            else:
                raise ValueError(
                    "Invalid filter '%s', must start with 'min' or 'max'" % name)
            if hasattr(self, field_name):
                field_value = getattr(self, field_name)
            else:
                print(self)
                raise ValueError(
                    "Invalid filter '%s' IsovarResult does not have property '%s'" % (
                        name,
                        field_name))
            filter_values_dict[name] = comparison_fn(field_value, threshold)
        return filter_values_dict

    def to_dict(self):
        """
        Dictionary representation of fields used to construct this IsovarResult

        Returns dict
        """
        return {
            k: getattr(self, k)
            for k in self.__slots__

        }

    def clone_with_new_field(self, **kwargs):
        """
        Create a copy of this IsovarResult object including any new
        parameters in `kwargs`.

        Returns IsovarResult
        """
        for (k, v) in self.to_dict().items():
            if k not in kwargs:
                kwargs[k] = v
        return IsovarResult(**kwargs)

    def clone_with_extra_filters(self, filter_thresholds):
        """
        Applies filters to properties of this IsovarResult and then creates
        a copy with an updated filter_values_dict field.

        Parameters
        ----------
        filter_thresholds : dict or OrderedDict
            Dictionary mapping filter names (e.g. "max_fraction_ref_reads) to
            thresholds.

        Returns IsovarResult
        """
        # first clone filter values which might already exist
        combined_filter_value_dict = OrderedDict()
        for k, v in self.filter_values_dict.items():
            combined_filter_value_dict[k] = v
        for k,v in self.apply_filters(filter_thresholds).items():
            combined_filter_value_dict[k] = v
        return self.clone_with_new_field(
            filter_values_dict=combined_filter_value_dict)

    @property
    def passes_all_filters(self):
        """
        Does this IsovarResult have True for all the filter values in
        self.filter_values_dict?
        """
        if len(self.filter_values_dict) == 0:
            return True
        else:
            return all(list(self.filter_values_dict.values()))

    @property
    def top_protein_sequence(self):
        """
        If any protein sequences were assembled for this variant then
        return the best according to coverage, number of mismatches
        relative to the reference, number of reference transcripts
        which match sequence before the variant and protein
        sequence length.

        Returns ProteinSequence or None
        """
        if len(self.sorted_protein_sequences) > 0:
            return self.sorted_protein_sequences[0]
        else:
            return None

    def to_record(self):
        """
        Create an OrderedDict of essential information from
        this IsovarResult to be used for building a DataFrame across
        variants.

        Returns OrderedDict
        """
        d = OrderedDict([
            ("variant", self.variant.short_description),
            ("variant_gene", ";".join(self.variant.gene_names))
        ])

        # get all quantitative fields from this object
        for key in dir(self):
            if key.startswith("num_") or key.startswith("fraction_") or key.startswith("ratio_"):
                d[key] = getattr(self, key)

        ########################################################################
        # predicted protein changes without looking at RNA reads
        ########################################################################
        effect = self.predicted_effect

        d["predicted_effect"] = effect.short_description
        d["predicted_effect_class"] = effect.__class__.__name__

        # list of field names on varcode effect properties
        effect_properties = [
            "gene_name",
            "gene_id",
            "transcript_id",
            "transcript_name",
            "modifies_protein_sequence",
            "original_protein_sequence",
            "aa_mutation_start_offset",
            "aa_mutation_end_offset",
            "mutant_protein_sequence"
        ]
        for field_name in effect_properties:
            # store effect fields with prefix 'predicted_effect_' and use
            # getattr in case the field is not available for all effects
            d["predicted_effect_%s" % field_name] = getattr(
                effect,
                field_name,
                None)

        ########################################################################
        # filters
        ########################################################################
        for filter_name, filter_value in self.filter_values_dict.items():
            d["filter:%s" % filter_name] = filter_value
        d["pass"] = self.passes_all_filters

        ########################################################################
        # get the top protein sequence, if one exists
        ########################################################################
        protein_sequence = self.top_protein_sequence

        # list of names we want to use in the result dictionary,
        # paired with names of fields on ProteinSequence
        protein_sequence_properties = [
            ("protein_sequence", "amino_acids"),
            ("protein_sequence_mutation_start", "variant_aa_interval_start"),
            ("protein_sequence_mutation_end", "variant_aa_interval_stop"),
            ("protein_sequence_ends_with_stop_codon", "ends_with_stop_codon"),
            ("protein_sequence_mismatches", "num_mismatches"),
            ("protein_sequence_mismatches_before_variant", "num_mismatches_before_variant"),
            ("protein_sequence_mismatches_after_variant", "num_mismatches_after_variant"),
            ("protein_sequence_num_supporting_reads", "num_supporting_reads"),
            ("protein_sequence_num_supporting_fragments", "num_supporting_fragments"),
        ]
        for (name, protein_sequence_field) in protein_sequence_properties:
            d[name] = getattr(protein_sequence, protein_sequence_field, None)

        return d

    def overlapping_transcripts(self, only_coding=True):
        """
        Transcripts which this variant overlaps.

        Parameters
        ----------
        only_coding : bool
            Only return transcripts which are annotated as coding for a
            protein (default=True)

        Returns set of pyensembl.Transcript objects
        """
        return {
            t
            for t in self.variant.transcripts
            if not only_coding or t.is_protein_coding
        }

    def overlapping_transcript_ids(self, only_coding=True):
        """
        Transcript IDs which this variant overlaps.

        Parameters
        ----------
        only_coding : bool
            Only return transcripts which are annotated as coding for a
            protein (default=True)
        Returns set of str
        """
        return {
            t.id
            for t in self.variant.transcripts
            if not only_coding or t.is_protein_coding
        }

    def overlapping_genes(self, only_coding=True):
        """
        Genes which this variant overlaps.

        Parameters
        ----------
        only_coding : bool
            Only return genes which are annotated as coding for a
            protein (default=True)

        Returns set of pyensembl.Gene objects
        """
        return {
            g
            for g in self.variant.genes
            if not only_coding or g.is_protein_coding
        }

    def overlapping_gene_ids(self, only_coding=True):
        """
        Gene IDs which this variant overlaps.

        Parameters
        ----------
        only_coding : bool
            Only return genes which are annotated as coding for a
            protein (default=True)

        Returns set of str
        """
        return {
            g.id
            for g in self.variant.genes
            if not only_coding or g.is_protein_coding
        }

    def transcripts_from_of_protein_sequences(self, protein_sequence_limit=None):
        """
        Ensembl transcript IDs of all transcripts which support the reading
        frame used by protein sequences in this IsovarResult.

        Parameters
        ----------
        protein_sequence_limit : int or None
            If supplied then only consider the top protein sequences up to
            this number.

        Returns list of str
        """
        transcript_set = set([])
        for p in self.sorted_protein_sequences[:protein_sequence_limit]:
            transcript_set.update(p.transcript_ids_supporting_protein_sequence)
        return sorted(transcript_set)

    def transcripts_from_protein_sequences(self, protein_sequence_limit=None):
        """
        Ensembl transcripts which support the reading frame used by protein
        sequences in this IsovarResult.

        Parameters
        ----------
        protein_sequence_limit : int or None
            If supplied then only consider the top protein sequences up to
            this number.

        Returns list of pyensembl.Transcript
        """
        genome = self.variant.genome
        transcript_ids = self.transcript_ids_used_by_protein_sequences(
            num_protein_sequences=protein_sequence_limit)
        return [
            genome.transcript_by_id(transcript_id)
            for transcript_id in transcript_ids
        ]

    def genes_from_protein_sequences(self, protein_sequence_limit=None):
        """
        Ensembl genes which support the reading frame used by protein
        sequences in this IsovarResult.

        Parameters
        ----------
        protein_sequence_limit : int or None
            If supplied then only consider the top protein sequences up to
            this number.

        Returns list of pyensembl.Gene
        """
        transcripts = self.transcripts_used_by_protein_sequences(
            protein_sequence_limit=protein_sequence_limit)
        genes = [t.gene for t in transcripts]
        return sorted(genes)

    def gene_ids_from_protein_sequences(self, protein_sequence_limit=None):
        """
        Ensembl genes IDs which support the reading frame used by protein
        sequences in this IsovarResult.

        Parameters
        ----------
        protein_sequence_limit : int or None
            If supplied then only consider the top protein sequences up to
            this number.

        Returns list of str
        """
        return [
            g.id
            for g
            in self.genes_from_protein_sequences(protein_sequence_limit=None)
        ]

    @property
    def ref_reads(self):
        """
        AlleleRead objects at this locus which support the reference allele
        """
        return self.read_evidence.ref_reads

    @property
    def alt_reads(self):
        """
        AlleleRead objects at this locus which support the mutant allele
        """
        return self.read_evidence.alt_reads

    @property
    def other_reads(self):
        """
        AlleleRead objects at this locus which support some allele other than
        either the reference or alternate.
        """
        return self.read_evidence.other_reads

    @property
    def ref_read_names(self):
        """
        Names of reference reads at this locus.
        """
        return {r.name for r in self.ref_reads}

    @property
    def alt_read_names(self):
        """
        Names of alt reads at this locus.
        """
        return {r.name for r in self.alt_reads}

    @property
    def ref_and_alt_read_names(self):
        """
        Names of reads which support either the ref or alt alleles.
        """
        return self.ref_read_names.union(self.alt_read_names)

    @property
    def other_read_names(self):
        """
        Names of other (non-alt, non-ref) reads at this locus.
        """
        return {r.name for r in self.other_reads}

    @property
    def all_read_names(self):
        """
        Names of all reads at this locus.
        """
        return self.ref_read_names.union(self.alt_read_names).union(self.other_read_names)

    @property
    def num_total_reads(self):
        """
        Total number of reads at this locus, regardless of allele.
        """
        return self.num_ref_reads + self.num_alt_reads + self.num_other_reads

    @property
    def num_total_fragments(self):
        """
        Total number of distinct fragments at this locus, which also corresponds
        to the total number of read names.
        """
        return len(self.all_read_names)

    @property
    def num_ref_reads(self):
        """
        Number of reads which support the reference allele.
        """
        return len(self.ref_reads)

    @property
    def num_ref_fragments(self):
        """
        Number of distinct fragments which support the reference allele.
        """
        return len(self.ref_read_names)

    @property
    def num_alt_reads(self):
        """
        Number of reads which support the alt allele.
        """
        return len(self.alt_reads)

    @property
    def num_alt_fragments(self):
        """
        Number of distinct fragments which support the alt allele.
        """
        return len(self.alt_read_names)

    @property
    def num_other_reads(self):
        """
        Number of reads which support neither the reference nor alt alleles.
        """
        return len(self.other_reads)

    @property
    def num_other_fragments(self):
        """
        Number of distinct fragments which support neither the reference nor
        alt alleles.
        """
        return len(self.other_read_names)

    @property
    def fraction_ref_reads(self):
        """
        Allelic fraction of the reference allele among all reads at this site.
        """
        return safediv(self.num_ref_reads, self.num_total_reads)

    @property
    def fraction_ref_fragments(self):
        """
        Allelic fraction of the reference allele among all fragments at this site.
        """
        return safediv(self.num_ref_fragments, self.num_total_fragments)

    @property
    def fraction_alt_reads(self):
        """
        Allelic fraction of the variant allele among all reads at this site.
        """
        return safediv(self.num_alt_reads, self.num_total_reads)

    @property
    def fraction_alt_fragments(self):
        """
        Allelic fraction of the variant allele among all fragments at this site.
        """
        return safediv(self.num_alt_fragments, self.num_total_fragments)

    @property
    def fraction_other_reads(self):
        """
        Allelic fraction of the "other" (non-ref, non-alt) alleles among all
        reads at this site.
        """
        return safediv(self.num_other_reads, self.num_total_reads)

    @property
    def fraction_other_fragments(self):
        """
        Allelic fraction of the "other" (non-ref, non-alt) alleles among all
        fragments at this site.
        """
        return safediv(self.num_other_fragments, self.num_total_fragments)

    @property
    def ratio_other_to_ref_reads(self):
        """
        Ratio of the number of reads which support alleles which are neither
        ref/alt to the number of ref reads.
        """
        return safediv(self.num_other_reads, self.num_ref_reads)

    @property
    def ratio_other_to_ref_fragments(self):
        """
        Ratio of the number of fragments which support alleles which are neither
        ref/alt to the number of ref fragments.
        """
        return safediv(self.num_other_fragments, self.num_ref_fragments)

    @property
    def ratio_other_to_alt_reads(self):
        """
        Ratio of the number of reads which support alleles which are neither
        ref/alt to the number of alt reads.
        """
        return safediv(self.num_other_reads, self.num_alt_reads)

    @property
    def ratio_other_to_alt_fragments(self):
        """
        Ratio of the number of fragments which support alleles which are neither
        ref/alt to the number of alt fragments.
        """
        return safediv(self.num_other_fragments, self.num_alt_fragments)

    @property
    def ratio_ref_to_other_reads(self):
        """
        Ratio of the number of reference reads to non-ref/non-alt reads
        """
        return safediv(self.num_ref_reads, self.num_other_reads)

    @property
    def ratio_ref_to_other_fragments(self):
        """
        Ratio of the number of reference fragments to non-ref/non-alt fragments
        """
        return safediv(self.num_ref_fragments, self.num_other_fragments)

    @property
    def ratio_alt_to_other_reads(self):
        """
        Ratio of alt allele reads to non-ref/non-alt reads
        """
        return safediv(self.num_alt_reads, self.num_other_reads)

    @property
    def ratio_alt_to_other_fragments(self):
        """
        Ratio of the number of fragments which support the alt allele
        to the number of non-alt/non-ref allele fragments.
        """
        return safediv(self.num_alt_fragments, self.num_other_fragments)


