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
This module wraps pysam and gives us a view of any reads overlapping
a variant locus which includes offsets into the read sequence & qualities
for extracting variant nucleotides.
"""

from __future__ import print_function, division, absolute_import

from .value_object import ValueObject
from .logging import get_logger

logger = get_logger(__name__)


class LocusRead(ValueObject):
    __slots__ = [
        "name",
        "sequence",
        "reference_positions",
        "quality_scores",
        "base0_read_position_before_variant",
        "base0_read_position_after_variant"
    ]

    def __init__(
            self,
            name,
            sequence,
            reference_positions,
            quality_scores,
            base0_read_position_before_variant,
            base0_read_position_after_variant):
        self.name = name
        self.sequence = sequence
        self.reference_positions = reference_positions
        self.quality_scores = quality_scores
        self.base0_read_position_before_variant = base0_read_position_before_variant
        self.base0_read_position_after_variant = base0_read_position_after_variant

    @classmethod
    def from_pysam_aligned_segment(
            cls,
            read,
            base0_position_before_variant,
            base0_position_after_variant,
            use_secondary_alignments,
            use_duplicate_reads,
            min_mapping_quality,
            use_soft_clipped_bases=False):
        """
        Create LocusRead object from pysam.AlignedSegment

        Parameters
        ----------
        read : pysam.AlignedSegment
        base0_position_before_variant : int
        base0_position_after_variant : int
        use_secondary_alignments : bool
        use_duplicate_reads : bool
        min_mapping_quality : int
        use_soft_clipped_bases : bool (optional

        Returns
        -------
        LocusRead or None
        """
        name = read.query_name
        if name is None:
            logger.warn(
                "Read missing name at position %d",
                base0_position_before_variant + 1)
            return None

        if read.is_unmapped:
            logger.warn(
                "How did we get unmapped read '%s' in a pileup?", name)
            return None

        if read.is_secondary and not use_secondary_alignments:
            logger.debug("Skipping secondary alignment of read '%s'", name)
            return None

        if read.is_duplicate and not use_duplicate_reads:
            logger.debug("Skipping duplicate read '%s'", name)
            return None

        mapping_quality = read.mapping_quality

        missing_mapping_quality = mapping_quality is None

        if min_mapping_quality > 0 and missing_mapping_quality:
            logger.debug("Skipping read '%s' due to missing MAPQ" % name)
            return None
        elif mapping_quality < min_mapping_quality:
            logger.debug(
                "Skipping read '%s' due to low MAPQ: %d < %d",
                read.mapping_quality,
                mapping_quality,
                min_mapping_quality)
            return None

        sequence = read.query_sequence

        if sequence is None:
            logger.warn("Read '%s' missing sequence", name)
            return None

        base_qualities = read.query_qualities

        if base_qualities is None:
            logger.warn("Read '%s' missing base qualities", name)
            return None

        # Documentation for pysam.AlignedSegment.get_reference_positions:
        # ------------------------------------------------------------------
        # By default, this method only returns positions in the reference
        # that are within the alignment. If full_length is set, None values
        # will be included for any soft-clipped or unaligned positions
        # within the read. The returned list will thus be of the same length
        # as the read.
        #
        # Source:
        # http://pysam.readthedocs.org/en/latest/
        # api.html#pysam.AlignedSegment.get_reference_positions
        #
        # We want a None value for every read position that does not have a
        # corresponding reference position.
        reference_positions = read.get_reference_positions(
            full_length=True)

        # pysam uses base-0 positions everywhere except region strings
        # Source:
        # http://pysam.readthedocs.org/en/latest/faq.html#pysam-coordinates-are-wrong
        if base0_position_before_variant not in reference_positions:
            logger.debug(
                "Skipping read '%s' because first position %d not mapped",
                name,
                base0_position_before_variant)
            return None
        else:
            base0_read_position_before_variant = reference_positions.index(
                base0_position_before_variant)

        if base0_position_after_variant not in reference_positions:
            logger.debug(
                "Skipping read '%s' because last position %d not mapped",
                name,
                base0_position_after_variant)
            return None
        else:
            base0_read_position_after_variant = reference_positions.index(
                base0_position_after_variant)

        if isinstance(sequence, bytes):
            sequence = sequence.decode('ascii')

        if not use_soft_clipped_bases:
            start = read.query_alignment_start
            end = read.query_alignment_end
            sequence = sequence[start:end]
            reference_positions = reference_positions[start:end]
            base_qualities = base_qualities[start:end]
            base0_read_position_before_variant -= start
            base0_read_position_after_variant -= start

        return cls(
            name=name,
            sequence=sequence,
            reference_positions=reference_positions,
            quality_scores=base_qualities,
            base0_read_position_before_variant=base0_read_position_before_variant,
            base0_read_position_after_variant=base0_read_position_after_variant)

    @classmethod
    def from_pysam_pileup_element(
            cls,
            pileup_element,
            base0_position_before_variant,
            base0_position_after_variant,
            use_secondary_alignments,
            use_duplicate_reads,
            min_mapping_quality,
            use_soft_clipped_bases=False):
        """
        Parameters
        ----------
        pileup_element : pysam.PileupRead

        base0_position_before_variant : int

        base0_position_after_variant : int

        use_secondary_alignments : bool

        use_duplicate_reads : bool

        min_mapping_quality : int

        use_soft_clipped_bases : bool. Default false; set to true to keep soft-clipped bases

        Returns LocusRead or None
        """
        # extract the AlignedSegment, throwing away information about where in the read
        # the current pileup occurs
        read = pileup_element.alignment


        # For future reference,  may get overlapping reads
        # which can be identified by having the same name
        name = read.query_name

        if pileup_element.is_refskip:
            # if read sequence doesn't actually align to the reference
            # base before a variant, skip it
            logger.debug("Skipping pileup element with CIGAR alignment N (intron), read name = %s")
            return None
        elif pileup_element.is_del:
            logger.debug(
                "Skipping deletion at position %d (read name = %s)",
                base0_position_before_variant + 1,
                pileup_element)
            return None

        return cls.from_pysam_aligned_segment(
            read=read,
            base0_position_before_variant=base0_position_before_variant,
            base0_position_after_variant=base0_position_after_variant,
            use_secondary_alignments=use_secondary_alignments,
            use_duplicate_reads=use_duplicate_reads,
            min_mapping_quality=min_mapping_quality,
            use_soft_clipped_bases=use_soft_clipped_bases)