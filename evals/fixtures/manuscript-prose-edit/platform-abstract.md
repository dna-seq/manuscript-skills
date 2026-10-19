# GenomeDesk: configurable local genome annotation

## Abstract

GenomeDesk is a local application for exploring published variant annotations. It combines configurable
reference packages, a browser interface and inspectable reports in a single workflow. Reference content
can be updated independently of application code. The platform is intended for research and teaching;
the runtime comparison does not establish the clinical validity of its annotations.

## Methods

We compared two application configurations on the same workstation and input genome. Each configuration
ran repeatedly from prepared local reference data. The comparison includes input parsing and report
generation. The configurations perform different annotation workloads, so their timings describe these
workflows rather than general performance of the underlying engines.

## Results

The new configuration took a median of 24.8 seconds over 10 runs; the earlier configuration took a median
of 4,033 seconds over 3 runs. The new configuration used 2.1 GB peak resident memory. A separate comparison
of 80 weighted scores on the same genome gave Pearson r = 0.99998 and a maximum absolute difference of
0.06. These observations concern one genome and do not test predictive performance across individuals.

## Discussion

The implementation separates reference content from the application and makes the selected sources
visible in the report. It is important to note that this separation is an important feature of the
platform. The timing comparison evaluates the tested configurations; it does not isolate the effects
of the individual design choices.
