Text2Gene
=========

Text2Gene was created to assist genetic curators and clinical scientists in gathering
relevant research for clinically-relevant human genetic variants.

Text2Gene allows you to input a DNA mutation string in HGVS format and find as many relevant
matches for the described variant as possible.  Text2Gene constructs powerful searches in a 
variety of different formats, matching even in older transcripts (illuminating pre-internet 
papers, for example) as well as finding the newest research not yet submitted to ClinVar.

* INPUT: HGVS string.
* OUTPUT: List of articles in PubMed about this variant. 

Text2Gene relies mainly on the following publicly-available resources to accomplish a high-precision search:

* Universal Transcript Archive
* ClinVar
* PubTator
* GoogleQuery

A number of well-tested, highly stable open source libraries are employed in making this system possible:

* metapub
* hgvs
* metavariant
* medgen-myqsl
* medgen

The above libraries are all Apache2 Licensed, in use in various institutions around the world, and
use Semantic Versioning.  As a result, these libraries constitute a firm foundation around which to
build a fairly robust system.

============
Requirements
============

Text2Gene runs on Python3 exclusively and has been primarily tested using Python3.6 and Python3.7.

Text2Gene also requires a MySQL server and (optionally) a Postgres server for running UTA locally (see setup steps for UTA below).


=====
Setup
=====

At this time the Text2Gene system is fairly complex to set up and build. 
Much more documentation is needed and is in the process of being written.

Overview:

1. Install and configure MySQL to allow connections
2. (Optional) Set up Universal Transcript Archive (UTA) locally.
3. Use `medgen-mysql` to create the ClinVar, Gene, Hugo, and PubTator databases.
4. Use Text2Gene's `setup.py` script to install requirements for running Text2Gene database setup scripts.
5. Follow the numbered Text2Gene database scripts found in `{repo}/sbin`
6. Get API Keys for NCBI and Google Query.

1. Install MySQL
----------------

It is highly recommended to install MySQL databases either on the same system as Text2Gene
or in a network-adjacent location to where Text2Gene will be installed.  Text2Gene's usage
of MySQL is deep and extensive (multiple involved queries per variant).  *Using an SSD for 
Text2Gene should be considered a high priority* when considering resources, as an SSD will 
likely save you hours per day in aggregate of lookup and indexing times.

Recommended disk allotment for MySQL: 1 TB

MINIMUM disk allotment for MySQL: 500 GB

The NCBI databases used by Text2Gene alone take up roughly 300 GB.  A good deal of indexing on
relevant columns helps keep complicated queries running optimally; the tradeoff is that the 
database footprints swell in size accordingly.

2. Install UTA Locally (optional but recommended)
-------------------------------------------------

Each variant requires several lookups against the Universal Transcript Archive created and 
maintained by the biocommons group (originally Reece Hart, created and open sourced at Invitae).

There is a publically available UTA provided by Invitae.  However, relying on this remote 
resource slows down ClinVitae database transformation time by a factor of 10, which is a huge
bottleneck for keeping your ClinVitae database up to date reliably.   (In the future, medgen-mysql
may not use UTA for this purpose, but for now this is what's up.)

Please visit the BioCommons page for UTA for information on how to set up UTA locally.
You can select to use Docker or to set up and load Postgres the old-fashioned way.

IMPORTANT: You must use the `uta_20171026` release for Text2Gene.  Ignore at your own peril!


3. Clone medgen-mysql and install databases
-------------------------------------------

(Note: You can do this step concurrently to step #4.)

Summary: Collect MedGen, ClinVar, PubTator, Hugo, and Gene databases.

First, follow the instructions in https://github.com/text2gene/medgen-mysql

If you installed UTA locally, set the UTA_HOST variable to where you put the database.
For example:

```
export UTA_HOST=localhost
```

Now install all relevant databases:

```
make gene
make hugo
make medgen
make PubTator
make clinvar
```

In aggregate, these steps could take anywhere between 15 minutes to 3 hours, depending on 
whether you installed MySQL on an SSD, whether you set up UTA locally, and how quickly
your system can download some very large files from NCBI over FTP and HTTP.


4. Clone Text2Gene and run setup.py
-----------------------------------

Summary: Clone this repo, then create a Python3 virtualenv and activate it.  Then do `python setup.py install`.

Example that works:

```
cd /path/to/this/repo
python3.7 -m venv ve
source ve/bin/activate
pip install -U pip
python setup.py
```

If you find that running `setup.py` breaks, PLEASE file an issue.  Chances are its an OS environment 
dependency that can be fixed with some quick installs.  Many issues on Ubuntu systems can be fixed with the 
following line:

```
sudo apt-get install python3-dev libbz2-dev libcurl4-openssl-dev liblzma-dev 
```

If you installed UTA yourself, set the UTA_HOST environment variable accordingly. For example

```
export UTA_HOST=localhost
```


5. Text2Gene database setup.

The numbered scripts ("n_*") contain the basic setup requirements to get Text2Gene running.

Work should be done on improving this experience and its log outputs for reasons that will 
be immediately obvious to any sysadmin or devops people in the audience.

Do the following in order:

```
mysql -uroot -p < sbin/01_create_t2g_database.sql
python sbin/02_init_cache.py
mysql -umedgen -pmedgen < sbin/03_clinvar_components_tables.sql
python sbin/04_create_clinvar_components_table.py
python sbin/06_dump_m2p_to_json.py
python sbin/07_create_m2p_components_tables.py
```

(You may ask, "what happened to number 05, why don't I run that?"  The answer is that 04_ runs 05_ automatically. I know, this is confusing.  Improvements will happen here.  Pull requests welcome...!)

At this point, with the exception of the GoogleQuery engine (next step), you should have a working Text2Gene system.  Yay!

Try it out by running the command-line script `hgvs2pmid`:

hgvs2pmid "NM_004448.2:c.2326_2327insTCT"


6. Get and set external API Keys.

NCBI Eutils API keys should be used to ensure fewer limits on usage of NCBI resources.  The `hgvs`, `metavariant` and `metapub` libraries all depend on Eutils API calls, and not using an API key means a limit of 3 queries per second.

Aquire an NCBI key here: https://www.ncbi.nlm.nih.gov/account/settings/

Two environment variables must be used to ensure distribution of your API keys amongst the libraries that use it:

```
export NCBI_API_KEY={your_key_here}
export _NCBI_URL_KEY={your_key_here}
```

You absolutely need a Google Cloud Services API Key to run the GoogleQuery portion of Text2Gene.

To do this, you have to create a Google Cloud Account and then turn on Google Search API as a service.  (TODO: instructions and screenshots to aid this process.)

Once you have your API key in hand, the place to configure it is within the text2gene config files -- just replace the one that's already there (any keys you find in the repo are out of date).  In the future this configuration will instead be done via environment variables, much like NCBI_API_KEY.

Look in `/path/to/repo/text2gene/config/*.ini` for the place to set the key.

NOTE: It is *highly* recommended to set up your API key to restrict based on IP address.

=============
Configuration
=============

The GoogleQuery api key and other configuration variables specific to Text2Gene are configured in 
`/path/to/repo/text2gene/config/*.ini`.  This structure allows you to create arbitrary environment
names and associate clumps of information with them in INI files. 

The default text2gene_ENV is 'DEV', so by default, the dev.ini file will be sourced.

To change the Text2Gene environment to PRD, you would do:

```
export text2gene_ENV='PRD'
```



==========
Validation
==========

The Text2Gene system has been validated in usage with the Monarch Initiative in a project 
with Associate Director Julie McMurry.

* https://medium.com/@MonarchInit/video-interview-with-monarchs-julie-mcmurry-f327afaab284
* Given the set of FA related genes (FANCA, FANCAN, etc...), fill as many clinically-studied variants as possible in these regions. 
* Per variant, find as many PMIDs as possible.
* Human expert review of each new variant added to the gene region, and each new PMID found for all variants in FA regions.
* Results: 15% increase in clinically relevant research for FANCA regions, NOT including 12% of PMIDs found which came from survey or methods papers (irrelevant for clinical significance).



