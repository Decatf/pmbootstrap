CC      = gcc
CFLAGS  =
RM      = rm -f


default: all

all: android_reboot

android_reboot: android_reboot.c
	$(CC) $(CFLAGS) -o android_reboot android_reboot.c

clean:
	$(RM) android_reboot