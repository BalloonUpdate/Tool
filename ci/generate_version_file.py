if __name__ == "__main__":
    from file import File
    from version import productName, productVersion

    output = File('version-file.txt')

    template = f'''# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=FixedFileInfo(
    # filevers and prodvers should be always a tuple with four items: (1, 2, 3, 4)
    # Set not needed items to zero 0.
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x4,
    # The general type of file.
    # 0x1 - the file is an application.
    fileType=0x1,
    # The function of the file.
    # 0x0 - the function is not defined for this fileType
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [StringTable(
          u'000004b0',
          [
            StringStruct(u'Comments', u''),
            StringStruct(u'CompanyName', u''),
            StringStruct(u'FileDescription', u''),
            StringStruct(u'FileVersion', u'1.0.0.0'),
            StringStruct(u'InternalName', u''),
            StringStruct(u'LegalCopyright', u''),
            StringStruct(u'LegalTrademarks', u''),
            StringStruct(u'OriginalFilename', u''),
            StringStruct(u'ProductName', u'{productName}'),
            StringStruct(u'ProductVersion', u'{productVersion}'),
            StringStruct(u'Assembly Version', u'1.0.0.0')
          ]
        )
      ]),
      VarFileInfo([VarStruct(u'Translation', [0, 1200])
    ])
  ]
)
'''

    with open(output.path, "w+", encoding="utf-8") as f:
        f.write(template)
