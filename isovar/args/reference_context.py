# Copyright (c) 2016. Mount Sinai School of Medicine
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

from __future__ import print_function, division, absolute_import

from .default_parameters import (
    MAX_REFERENCE_TRANSCRIPT_MISMATCHES,
    MIN_TRANSCRIPT_PREFIX_LENGTH
)

def add_reference_context_args(
        parser,
        max_reference_transcript_mismatches_arg="--max-reference-transcript-mismatches",
        max_reference_transcript_mismatches_default=MAX_REFERENCE_TRANSCRIPT_MISMATCHES,
        min_transcript_prefix_length_arg="--min-transcript-prefix-length",
        min_transcript_prefix_length_default=MIN_TRANSCRIPT_PREFIX_LENGTH):
    """
    Extends an ArgumentParser instance with the following commandline arguments:
        --max-reference-transcript-mismatches
        --min-transcript-prefix-length
    """
    reference_context_group = parser.add_argument_group("Reference Transcripts")
    reference_context_group.add_argument(
        max_reference_transcript_mismatches_arg,
        type=int,
        default=max_reference_transcript_mismatches_default,
        help=(
            "Maximum number of mismatches between variant sequence"
            " reference sequence before a candidate reading frame is ignored."))

    reference_context_group.add_argument(
        min_transcript_prefix_length_arg,
        type=int,
        default=min_transcript_prefix_length_default,
        help=(
            "Number of nucleotides before the variant we try to match against "
            "a reference transcript. Values greater than zero exclude variants "
            "near the start codon of transcrPROTEIN_SEQUENCE_LEGNTHipts without 5' UTRs."))
    return parser
