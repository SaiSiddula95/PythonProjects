import os
import subprocess
import re
import logging
from pathlib import Path
from xml.dom import minidom

# --- CONFIGURATION ---
SAXON_JAR = "G:/Libraries/saxon-he-12.5.jar"  #  Update this with your actual Saxon JAR file
LOG_FILE = "error_log.txt"  #  Log file to store any transformation/validation errors

# --- GLOBAL TRACKERS ---
validation_errors = {}     # Stores XML files that fail XSD validation
unmatched_files = []       # Stores XML files that had no matching XSLT

# --- SETUP LOGGING ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

#  Load all .xsl/.xslt files from the given directory
def load_xslt_files(xslt_dir):
    return [f for f in os.listdir(xslt_dir) if f.endswith(".xsl") or f.endswith(".xslt")]

#  Extract prefix from filename, remove digits, and match using "contains" logic
def find_matching_xslt(xml_filename, xslt_files):
    base_name = Path(xml_filename).stem  # Get filename without extension
    prefix_clean = re.sub(r'\d+', '', base_name).strip().upper()  # Clean digits & uppercase

    for xslt in xslt_files:
        xslt_upper = xslt.strip().upper()
        #Hotfix a case where MESSAGE will match MESSAGESTATUS.xslt. Want to make sure both have status or both don't.
        statusExist = "STATUS" in prefix_clean.upper() and "STATUS" in xslt_upper
        if prefix_clean in xslt_upper and statusExist:
            return xslt  #  Match found
    return None  #  No match

# ✨ Run xmllint to pretty-print and overwrite original XML
def format_with_xmllint(file_path: Path):
    temp_path = file_path.parent / "temp.xml"

    format_cmd = ["xmllint", "--format", str(file_path), "-o", str(temp_path)]
    move_cmd = ["mv", str(temp_path), str(file_path)]

    try:
        subprocess.run(format_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(move_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"✨ Formatted XML using xmllint: {file_path}")
    except subprocess.CalledProcessError as e:
        print(f" xmllint formatting failed: {e.stderr.decode().strip()}")
        logging.error(f"xmllint formatting failed for {file_path}: {e.stderr.decode().strip()}")

#  Validate an XML file against an XSD schema using xmllint
def validate_xml_schema(file_path: Path, schema_path: Path):
    command = [
        "xmllint",
        "--noout",
        "--schema",
        str(schema_path),
        str(file_path)
    ]

    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        stdout = result.stdout.decode().strip()
        stderr = result.stderr.decode().strip()

        if result.returncode == 0:
            print(f" XML is valid: {file_path}")
        else:
            error_msg = stderr or stdout or "Validation failed with unknown error."
            print(f" XML failed validation: {file_path}\n{error_msg}")
            validation_errors[str(file_path)] = error_msg

    except Exception as e:
        print(f" Exception during schema validation: {file_path}\n{str(e)}")
        validation_errors[str(file_path)] = str(e)

#  Main function to transform, format, and validate one XML file
def process_file(input_file_path, output_file_path, xslt_path, schema_path=None):
    command = [
        "java", "-jar", SAXON_JAR,
        f"-s:{str(input_file_path)}",
        f"-xsl:{str(xslt_path)}",
        f"-o:{str(output_file_path)}"
    ]

    try:
        #  Transform using Saxon
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        print(f" Transformed: {input_file_path.name} → {output_file_path}")

        #  Format using xmllint
        format_with_xmllint(output_file_path)

        #  Schema validation (optional)
        if schema_path:
            validate_xml_schema(output_file_path, schema_path)

        return True
    except subprocess.CalledProcessError as e:
        error = e.stderr.decode().strip()
        print(f" Error transforming {input_file_path}:\n{error}")
        logging.error(f"{input_file_path} - {error}")
        return False

#  Builds destination path in a sibling 'Modified' directory
def ensure_output_path(input_file_path: Path, root_dir: Path, modified_folder_name: str):
    relative_path = input_file_path.relative_to(root_dir)
    modified_base = root_dir.parent / modified_folder_name
    output_file_path = modified_base / relative_path

    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    # Set write permissions to avoid Saxon write errors
    try:
        output_file_path.parent.chmod(0o755)
    except Exception as e:
        print(f" Failed to set folder permissions: {output_file_path.parent} — {e}")

    return output_file_path

#  Walks through all files, applies transformation if matched, logs unmatched
def traverse_and_process(root_dir: Path, xslt_dir: Path, modified_folder_name: str, schema_path: Path = None):
    xslt_files = load_xslt_files(xslt_dir)

    for current_dir, subdirs, files in os.walk(root_dir):
        current_path = Path(current_dir)

        # Skip the output folder to prevent self-processing
        if modified_folder_name in current_path.parts:
            continue

        for file in files:
            if file.lower().endswith(".xml"):
                input_file_path = current_path / file
                matching_xslt = find_matching_xslt(file, xslt_files)

                if not matching_xslt:
                    print(f" No matching XSLT for: {file}")
                    logging.error(f"No matching XSLT for {file}")
                    unmatched_files.append(str(input_file_path))
                    continue

                xslt_path = xslt_dir / matching_xslt
                output_file_path = ensure_output_path(input_file_path, root_dir, modified_folder_name)

                success = process_file(input_file_path, output_file_path, xslt_path, schema_path)

                if not success:
                    print(f" Skipping file due to error: {input_file_path}")

#  Write validation errors to a formatted report
def write_validation_report_to_txt():
    if not validation_errors:
        print(" No validation errors. No report generated.")
        return

    script_dir = Path(__file__).resolve().parent
    report_path = script_dir / "validation_report.txt"

    max_file_len = max(len(str(fp)) for fp in validation_errors)
    max_error_len = max(len(err) for err in validation_errors.values())
    separator = "+" + "-" * (max_file_len + 2) + "+" + "-" * (max_error_len + 2) + "+"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(" XML Schema Validation Error Report\n")
        f.write(separator + "\n")
        f.write(f"| {'File Path'.ljust(max_file_len)} | {'Error'.ljust(max_error_len)} |\n")
        f.write(separator + "\n")

        for filepath, error in validation_errors.items():
            f.write(f"| {filepath.ljust(max_file_len)} | {error.ljust(max_error_len)} |\n")

        f.write(separator + "\n")

    print(f" Validation report written to: {report_path}")

#  Write unmatched XML files to a report
def write_unmatched_files_report():
    if not unmatched_files:
        print(" All XML files matched with XSLTs.")
        return

    script_dir = Path(__file__).resolve().parent
    report_path = script_dir / "unmatched_files_report.txt"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(" Unmatched XML Files (no matching XSLT):\n\n")
        for filepath in unmatched_files:
            f.write(f"{filepath}\n")

    print(f" Unmatched files report written to: {report_path}")

#  MAIN SCRIPT EXECUTION
if __name__ == "__main__":
    #  Set paths here
    root_dir = Path("G:/Udemy/Python/TestFolder/XMLTransform/RootDir")
    xslt_dir = Path("G:/Udemy/Python/TestFolder/XMLTransform/XSLTDir")
    schema_path = Path("G:/Udemy/Python/TestFolder/XMLTransform/Message.xsd")
    modified_folder_name = "Modified"

    #  Begin processing
    traverse_and_process(root_dir, xslt_dir, modified_folder_name, schema_path)

    #  Generate reports
    write_validation_report_to_txt()
    write_unmatched_files_report()
