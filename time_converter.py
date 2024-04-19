# Function to calculate milliseconds into minutes and seconds
def ms_convert(duration: int) -> str:
    """
    Time converter to convert milliseconds into a list of minutes and seconds
    
    Returns minutes and seconds in str format: ```mm:ss```, ```02:06```
    """
    # time conversion for item length
    mill_sec = duration
    total_sec = mill_sec / 1000
    mins = int(total_sec // 60)
    secs = int(total_sec % 60)

    # apply zfill to get minutes and seconds in 00 format and change to string
    converted_time = str(mins).zfill(2) + ":" + str(secs).zfill(2)

    return converted_time