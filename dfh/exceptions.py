class SourceRecordParseError(ValueError):
    """Custom exception to raise when source METS XML cannot be parsed."""


class MissingTextBitstreamError(Exception):
    """Custom exception to raise when fulltext bitstream not found in DSpace METS.

    A typical 'good' METS file will contain a 'fileGrp' section that looks roughly like
    the following, allowing us to extract a bitstream UUID for the 'TEXT' bitstream via
    an embedded URL:

    ...
    <fileGrp USE="TEXT">
     <file ADMID="FT_1721.1_32272_4"
        CHECKSUM="76a261fadb68d3f9d36b3ed4cb26562b" CHECKSUMTYPE="MD5"
        GROUPID="GROUP_BITSTREAM_1721.1_32272_4"
        ID="BITSTREAM_TEXT_1721.1_32272_4" MIMETYPE="text/plain" SEQ="4"
        SIZE="233039">
       <FLocat LOCTYPE="URL"
        xlink:href="https://.../bitstreams/401e42c9-6ec1-45d4-889b-7689bd5be8c7/download"
        xlink:type="simple"
       />
     </file>
    </fileGrp>
    ...

    If we cannot find this bitstream UUID for any reason, this exception is raised.
    """
