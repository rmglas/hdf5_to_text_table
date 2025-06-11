#!/usr/bin/env python3

"""Convert HDF5 data into a table in text format

Read all one-dimensional data from the given HDF5 file and
write it into a table in text format. Each dataset will be
converted into a column inside the table.

We support HDF5 datasets and groups, and consider only
one-dimensional data with more than one element.
"""


VERBOSE = False


def main():
    args = parse_args()

    if args.verbose:
        global VERBOSE
        VERBOSE = True

    data = read_hdf5_file(args.filename)

    columns = args.columns.split(",") if args.columns is not None else []
    precision = args.precision.split(",") if args.precision is not None else []
    ignore = args.ignore.split(",") if args.ignore is not None else []

    data = filter_data(data, ignore, columns)

    if len(columns) == 0:
        columns = sorted([d["tree"] for d in data])
        for d in data:
            d["pos"] = columns.index(d["tree"])

    if len(precision) == 0:
        precision = ["10.3e" for c in columns]
    elif len(precision) == 1:
        precision = [precision[0] for c in columns]
    elif len(precision) != len(columns):
        raise ValueError(
            "number of precision format strings is "
            f"{len(precision):d} but does not match number of "
            f"columns of {len(columns):d}"
        )

    data.sort(key=lambda d: d["pos"])

    table = build_table(data, precision, args.number)

    header = create_header(data, args.number, args.full_name)

    table = convert_to_text(table, header, args.delimiter)

    if len(table) == 0:
        print_func("exit because table has no entries")
        return

    if args.preview:
        for line in table:
            print(line)

    filename_out = (
        args.output
        if args.output is not None
        else ".".join(args.filename.split(".")[:-1])
        + ".txt"  # replace extension with txt
    )
    write_table(table, filename_out, args.overwrite)

    return 0


main.__doc__ = __doc__


def print_func(*args, **kwargs):
    """Print only if VERBOSE is True"""

    if VERBOSE:
        print(*args, **kwargs)


def parse_args():
    """Parse command-line arguments"""

    import argparse

    parser = argparse.ArgumentParser(
        prog="hdf5_to_text_table",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("filename")
    parser.add_argument(
        "-o",
        "--output",
        help="output file (based on input filename if not given)",
    )
    parser.add_argument(
        "-c", "--columns", help="comma-separated list of columns"
    )
    parser.add_argument(
        "-p",
        "--precision",
        help="precision format string (either one for all columns, "
        "or a comma-separated list of format strings)",
    )
    parser.add_argument(
        "--ignore",
        help="comma-separated list of data entries to be ignored",
    )
    parser.add_argument(
        "--delimiter",
        help="delimiter (default is four spaces)",
        default="    ",
    )
    parser.add_argument(
        "-f",
        "--full-name",
        action="store_true",
        help="use full tree description as name in header",
    )
    parser.add_argument(
        "-n", "--number", action="store_true", help="number all rows"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="explain what is being done",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="overwrite existing output file",
    )
    parser.add_argument(
        "--preview", action="store_true", help="preview table in terminal"
    )

    return parser.parse_args()


def read_hdf5_file(filename):
    """Read data from HDF5 file

    Return a list of dictionaries with data and metadata
    (like name and tree name) for each data entry.

    So far, we support HDF5 datasets and groups.
    """

    import h5py
    import numpy

    data = []

    def loop(elements, tree):
        for e in elements:
            subtree = f"{tree:s}/{e:s}"
            element = elements[e]
            if isinstance(element, h5py.Dataset):
                data.append(
                    {
                        "name": e,
                        "tree": subtree,
                        "data": numpy.asarray(element),
                    }
                )
            elif isinstance(element, h5py.Group):
                loop(element, subtree)
            else:
                print_func(
                    f"cannot parse {e:s} of type " f"{str(type(element)):s}"
                )

    with h5py.File(filename, "r") as inputfile:
        loop(inputfile, "")

    return data


def filter_data(data, ignore, columns):
    """Filter data

    If ignore is not an empty list, we ignore all data
    entries that either have their name or tree name in the
    ignore list.

    If columns is a list, we select only data entries
    that have their name or tree name in columns.
    """

    data_parsed = []

    for d in data:
        if d["data"].ndim != 1:
            print_func(
                f"ignore data {d['tree']:s} with dimension "
                f"{d['data'].ndim:d} unequal 1"
            )
            continue
        elif d["data"].size == 1:
            print_func(f"ignore data {d['tree']:s} with size 1")
            continue

        for i in ignore:
            if i in [d["name"], d["tree"]]:
                print_func(f"ignore data {d['tree']:s}")
                continue

        if len(columns) > 0:
            if d["tree"] in columns:
                d["pos"] = columns.index(d["tree"])
            elif d["name"] in columns:
                d["pos"] = columns.index(d["name"])
            else:
                print_func(
                    f"ignore data {d['tree']:s} which was not "
                    "specified in columns"
                )
                continue

        data_parsed.append(d)

    return data_parsed


def build_table(data, precision, number):
    """Build the table for the given data

    This function returns a list of rows (or lines) with
    each row corresponding to a list of the column entries.

    For each column we apply the given precision format
    string (provided in a list, one precision per column).

    If number is True, we insert line numbers at the
    beginning of each row.
    """

    table = []

    max_rows = max([d["data"].size for d in data])

    for n in range(max_rows):
        line = []

        if number:
            line.append(f"{n+1:{len(str(max_rows))}d}")

        for p, d in zip(precision, data):
            try:
                value = d["data"][n]
            except IndexError:
                line.append("-")
            else:
                line.append(f"{value:{p}}")

        table.append(line)

    return table


def create_header(data, number, full_name):
    """Create header for table

    The header consists of the names of each column. If
    full_name is True, we use the tree name for the header.
    """

    header = []

    if number:
        header.append("#")

    for d in data:
        if full_name:
            header.append(d["tree"])
        else:
            header.append(d["name"])

    return header


def convert_to_text(table, header, delimiter):
    """Convert rows in table to text

    The input table is a list containing rows (or lines)
    which themselves are lists of column entries. These
    inner lists are converted to strings by concatenating
    the elements with the given delimiter.

    Also we take care that columns have the correct size
    (length) and we insert an additional line with "-"
    between the header and the table body.
    """

    column_sizes = [len(col) for col in header]

    for line in table:
        for i, col in enumerate(line):
            column_sizes[i] = max(column_sizes[i], len(col))

    table_text = []

    for line in [header]:
        line_columns = [
            f"{col:^{colsize}s}" for col, colsize in zip(line, column_sizes)
        ]
        line_text = delimiter.join(line_columns)
        table_text.append(line_text.rstrip())

    table_text.append(
        "-" * (sum(column_sizes) + (len(column_sizes) - 1) * len(delimiter))
    )

    for line in table:
        line_columns = [
            f"{col:>{colsize}s}" for col, colsize in zip(line, column_sizes)
        ]
        line_text = delimiter.join(line_columns)
        table_text.append(line_text.rstrip())

    return table_text


def write_table(table, filename, overwrite):
    """Write table to file"""

    import os.path

    if os.path.exists(filename) and not overwrite:
        raise OSError(
            f"file already exists: {filename:s} "
            "(use --overwrite to overwrite)"
        )

    with open(filename, "w") as outputfile:
        for line in table[:-1]:
            outputfile.write(line + "\n")
        outputfile.write(table[-1])

    print_func(f"write to file {filename:s}")


if __name__ == "__main__":
    import sys

    sys.exit(main())
