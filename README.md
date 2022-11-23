# cEdgeMigration

## Overview
This set of scripts completes two tasks for vEdge to cEdge migration.
1. migrate_templates.py reads variables from existing deployed vEdges, maps and attaches to cEdge templates
2. deploy_edges.py pushes bootstrap files to cEdges and boots them into Controller mode

## Installation Instructions

Clone repository
> git clone https://github.com/dbrown92700/cEdgeMigration

Recommended to create a virtual environment
> python -m venv venv

Install requirements
> pip install -r requirements.txt

## Migration Instructions

The migration script does the following:
- Prompts the user for several environment settings.  Some settins are used only for deployment.
Settings include source vManage, destination vManage (which can be the same as the source), credentials, vEdge credentials
(to be used for deployment), hostname prefix and suffix to change between vEdge and cEdge, 
and the amount of time to pause between subsequent passes when deploying the edges
- Prompts the user for the csv filename in WorkingDir to process
- Reads the list of vEdges from the file
- Reads the vEdge template variables
- Maps variables to cEdge template using the Map Files
- Attaches the cEdge template and downloads the bootstrap file

### Map File Formats

- Create a csv file for every cEdge template.  The file name should be the template name .csv
- The CSV column headers should be the same as the template csv download file with the following modifications:
  - Change column 1 to templateName1
  - Remove columns 2 & 3
- Create a row for each vEdge template that will map to this cEdge template
  - Column 1 should contain the vEdge template name
  - The remaining columns contain one of 3 options
  1. The vEdge template header that maps directly to the cEdge variable
  2. A constant value that will get mapped to every cEdge using the format (EQ _VALUE_)
  3. A variable name that will be filled out in the migrate list CSV using the format (VAR _VARIABLE_NAME_)
- Place the Map files in the MapFiles directory
- Example map files are provided

### Migrate List CSV

To migrate a set of vEdges to cEdges, create a CSV file with the following format and place it in the WorkingDir

- CSV Headers include at a minimum:
  - host-name1: vEdge hostname
  - uuid2: cEdge UUID
  - templateName2: cEdge Template Name
- If the cEdge Template has VAR fields, the headers must include each _VARIABLE_NAME_
- An example migrate list csv is provided

### Migration Execution

Once the map csv files are complete and a migrate list file is complete, execute migrate_templates.py.

> python migrate_templates.py

cEdge templates should be attached in vManage and the bootstrap files should be downloaded to WorkingDir.

## Deploy Instructions

The assumption of the deploy_edges.py script is that IOS devices are online, configured and reachable using the system-ip
that the cEdge will configured with (this could be the current management interface or a loopback
interface), and have a working set of credentials.

To execute the script:
- Place all of the target boostrap files in a sub-directory created under WorkingDir
- Execute:
> python deploy_edges.py

The script will:
- Read each of the bootstrap files for hostname, uuid and system-ip information
- Ping each system-ip to test reachability
- ssh to each system-ip using the configured credentials
- SCP each boostrap file to the correct router
- Issue the "controller-mode enable" command
- Monitor vManage for registration status of the edge
- Continue to iterate through these steps until all edges are registered
