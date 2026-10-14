"""TURMO baud-rate diagnostic. CLOSE TURMO Control before running.
Usage: py -3 baud_test.py COM3
Only tests known serial speeds, restores nothing persistent in the device.
"""
import sys, time, os
from PIL import Image, ImageDraw
from driver import Display
def main():
    if len(sys.argv)!=2:
        print("Usage: py -3 baud_test.py COM3")
        return 2
    port=sys.argv[1].upper()
    if not port.startswith('COM') or not port[3:].isdigit():
        print("Invalid COM port")
        return 2
    image=Image.new('RGB',(480,320),'#102030')
    d=ImageDraw.Draw(image)
    for y in range(0,320,8):
        d.rectangle((0,y,479,y+3),fill=(y%255,(y*3)%255,(y*7)%255))
    print('Test port:',port,'(close TURMO Control first)')
    for baud in (115200,460800,921600,2000000):
        os.environ['TURMO_BAUD']=str(baud)
        try:
            with Display(port) as display:
                # A single actual full-frame send; no symmetric-image flip.
                display.send(image)
                stats=display.last_stats
                if stats['bytes'] < 300000 or stats['mode'] != 'full':
                    print(f'{baud}: INVALID measurement: {stats}')
                else:
                    secs=stats['seconds']
                    print(f'{baud}: {stats["bytes"]/1024:.0f} KiB, '
                          f'{secs:.3f}s, {1/max(secs,0.001):.2f} FPS, '
                          f'{stats["bytes"]/1024/max(secs,0.001):.0f} KiB/s')
        except Exception as e:
            print(f'{baud}: FAILED ({type(e).__name__}: {e})')
        time.sleep(.5)
    print('Done. If display stops responding, unplug and reconnect its USB cable.')
if __name__=='__main__':
    raise SystemExit(main())
