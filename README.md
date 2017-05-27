# instagram_batch_downloader
A python script which allows you to download all the photos and video under an instagram user's page.


## Dependencies
+ [python]
+ [requests]

## usage:
+ -u username  
    The username. eg: NASA, adidas

+ -t download_type  
    An integer which indicates the download_type.  
    1 for video  
    2 for photo  
    3 for both  
    The default value is 3.

+ -m max_page:  
    The maximum number of pages that you want to download.  
    The default value is 9999.  
    Normally each page contains 12 files

+ -C  
    Continue the last download


## examples:
```python
python3 go_spider.py -u nasa -m 5 -t 3
```

```python
python3 go_spider.py -C
```
[requests]:https://github.com/kennethreitz/requests
[python]:https://www.python.org/