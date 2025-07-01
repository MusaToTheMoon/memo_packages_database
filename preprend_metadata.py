file_name = "android.app.Service"
source_type = "foo1"
url = "foo2"
source_code = "example java source code"
with open("prepend_metadata_experiment.txt", 'w') as f:
    # metadata = f"\n// File : {file_name}\n// Source Type : foo\n\n"
    metadata = (
        f"// file_name   : {file_name}\n"
        f"// source_type : {source_type}\n"
        f"// url         : {url}\n\n"
    )

    f.write(metadata + source_code)
