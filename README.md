# S3 Glacier Storage Restoring

A single-file (<200 loc) python script to restore S3 files stored with the GLACIER Storage Class.

## Install

No pip yet, it's just a simple script. Either download the script or `git clone`. It only requires `boto3` and `Click`:

```bash
$ pip install -r requirements.txt
```

## Usage

I've quickly hacked a CLI tool, but I encourage you to just look at the code and define your own `__main__` using the primitive `S3GlacierClient` with your own usage. Anyways, here are the docs:

Assuming the following variables:

```
BUCKET_NAME: The name of the bucket containing your objects (REQUIRED)
PREFIX: Optionally, all operations are done using this prefix (OPTIONAL)
```


##### Restore a single object

```bash
$ python s3_glacier.py -b BUCKET_NAME restore-single-object "My Files/My Movies/Escape_From_New_York.mp4"
SUCCESS Restored object: My Files/My Movies/Escape_From_New_York.mp4
```

##### Restore multiple objects

Potentially restore EVERY object in the bucket. Keep in mind that this is a recursive operation.

```bash
$ python s3_glacier.py -b BUCKET_NAME restore-objects
SUCCESS Restored object: My Files/My Movies/Escape_From_New_York.mp4
SUCCESS Restored object: My Files/My Movies/Godfather_I.mp4
SUCCESS Restored object: My Files/My Movies/Godfather_II.mp4
SUCCESS Restored object: My Files/My Movies/Godfather_III.mp4
```

##### Check restore status of a single object
```bash
$ python s3_glacier.py -b BUCKET_NAME is-object-restored "My Files/My Movies/Escape_From_New_York.mp4"
Restore in progres...
```

##### Check restore status of all objects

```bash
$ python s3_glacier.py -b BUCKET_NAME check-restore-status
Checking status of bucket. This operation can take some time if there are too many files.
Restore in progress...
Restore in progress...
Restore in progress...
Done!
```