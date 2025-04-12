# Import standard libraries for file handling, subprocesses, regex, logging, and XML formatting
import os
import subprocess
import re
import logging
from pathlib import Path
from xml.dom import minidom

# -- CONFIGURATION --
SAXON_JAR = "/absolute/path/to/saxon.jar"  # 🔧 Path to your Saxon JAR file for XSLT transformation
LOG_FILE = "error_log.txt"  # 🔧 Log file to store errors from processing

# -- SETUP LOGGING --
logging.basicConfig(
    filename=LOG_FILE,  # Log errors to this file
    level=logging.ERROR,  # Only log ERROR level and above
    format="%(asctime)s - %(levelname)s - %(message)s"  # Log format with time and message
)

def load_xslt_files(xslt_dir):
    """Loads all .xsl and .xslt files from the given directory."""
    return [f for f in os.listdir(xslt_dir) if f.endswith(".xsl") or f.endswith(".xslt")]

def find_matching_xslt(xml_filename, xslt_files):
    """
    Cleans the filename, removes digits, uppercases it, and finds
    the first XSLT whose name contains the cleaned prefix.
    """
    base_name = Path(xml_filename).stem  # Get filename without extension
    prefix_clean = re.sub(r'\d+', '', base_name).strip().upper()  # Remove digits, trim, uppercase

    for xslt in xslt_files:
        xslt_upper = xslt.strip().upper()  # Sanitize and uppercase the xslt filename
        print(f"🧪 Testing match: '{prefix_clean}' in '{xslt_upper}'")  # Debug log

        if prefix_clean in xslt_upper:  # Substring match
            print(f"✅ Match found: {prefix_clean} in {xslt}")  # Match found log
            return xslt  # Return matched XSLT

    print(f"❌ No match found for: {prefix_clean}")  # No match found
    return None  # Return None if no XSLT matched

def pretty_print_xml(file_path: Path):
    """
    Reads an XML file and re-writes it with pretty indentation.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            raw_xml = f.read()  # Read the raw XML content

        parsed = minidom.parseString(raw_xml)  # Parse the XML using DOM
        pretty_xml = parsed.toprettyxml(indent="  ")  # Re-format with indentation

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)  # Overwrite the file with pretty-printed XML

        print(f"✨ Pretty-printed: {file_path}")  # Success log
    except Exception as e:
        logging.error(f"Failed to pretty-print {file_path}: {e}")  # Log any formatting error
        print(f"⚠️ Pretty-print failed for {file_path}")  # Display formatting failure

def process_file(input_file_path, output_file_path, xslt_path):
    """
    Calls the Saxon JAR using subprocess to transform an XML file.
    """
    # Prepare the Java command with saxon args
    command = [
        "java", "-jar", SAXON_JAR,
        f"-s:{str(input_file_path)}",  # Input XML
        f"-xsl:{str(xslt_path)}",      # XSLT to apply
        f"-o:{str(output_file_path)}"  # Output XML path
    ]

    try:
        # Run the command with a timeout and capture output
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30  # Timeout to prevent hangs
        )
        print(f"✅ Transformed: {input_file_path.name} → {output_file_path}")  # Success message

        pretty_print_xml(output_file_path)  # Re-format the output XML
        return True  # Transformation successful
    except subprocess.CalledProcessError as e:
        # Log transformation failure
        error = e.stderr.decode().strip()
        print(f"💥 Error transforming {input_file_path}:\n{error}")
        logging.error(f"{input_file_path} - {error}")
        return False  # Return failure status

def ensure_output_path(input_file_path: Path, root_dir: Path, modified_folder_name: str):
    """
    Generates and creates the output path for a file in the Modified folder,
    keeping the same relative structure.
    """
    relative_path = input_file_path.relative_to(root_dir)  # Get path relative to root_dir
    output_file_path = root_dir / modified_folder_name / relative_path  # Build destination path
    output_file_path.parent.mkdir(parents=True, exist_ok=True)  # Create directories if needed
    return output_file_path  # Return full destination path for output file

def traverse_and_process(root_dir: Path, xslt_dir: Path, modified_folder_name: str):
    """
    Recursively walk through root_dir, transform all XML files using
    matching XSLT, and save them in a sibling 'Modified' folder.
    """
    xslt_files = load_xslt_files(xslt_dir)  # Load all xslt files once

    for current_dir, subdirs, files in os.walk(root_dir):  # Walk every folder/file in root_dir
        current_path = Path(current_dir)  # Convert to Path object for safety

        # Avoid processing the Modified folder itself
        if modified_folder_name in current_path.parts:
            continue  # Skip Modified folder

        for file in files:
            if file.lower().endswith(".xml"):  # Process only XML files
                input_file_path = current_path / file  # Full path to input file
                matching_xslt = find_matching_xslt(file, xslt_files)  # Try to find a matching XSLT

                if not matching_xslt:
                    print(f"❌ No matching XSLT for: {file}")  # No XSLT matched
                    logging.error(f"No matching XSLT for {file}")  # Log it
                    continue  # Skip to next file

                xslt_path = xslt_dir / matching_xslt  # Full path to matching XSLT
                output_file_path = ensure_output_path(input_file_path, root_dir, modified_folder_name)  # Determine destination path

                success = process_file(input_file_path, output_file_path, xslt_path)  # Transform and pretty-print
                if not success:
                    print(f"⚠️ Skipping file due to error: {input_file_path}")  # Warn if error occurred

# -- MAIN EXECUTION --
if __name__ == "__main__":
    # Define input/output/config folders (replace with your actual paths)
    root_dir = Path("/home/documents/foo/projectroot/foldertoprocess")  # 🔧 Root folder of XMLs
    xslt_dir = Path("/home/configs/xslts/")  # 🔧 Location of your XSLT files
    modified_folder_name = "Modified"  # 🔧 Destination folder name within root_dir

    # Start the transformation process
    traverse_and_process(root_dir, xslt_dir, modified_folder_name)
