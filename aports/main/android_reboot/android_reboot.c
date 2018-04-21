/* vi: set sw=4 ts=4: */
/*
 * Stuff shared between init, reboot, halt, and poweroff
 *
 * Copyright (C) 1999-2004 by Erik Andersen <andersen@codepoet.org>
 *
 * Licensed under GPL version 2, see file LICENSE in this tarball for details.
 */

#include <errno.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <asm/unistd.h>
#include <linux/reboot.h>
#include <sys/reboot.h>
#include <sys/syslog.h>

const char * const init_sending_format = "Sending SIG%s to all processes.";
const char * const bb_shutdown_format = "\r%s\n";

int bb_shutdown_system(/* unsigned long magic */)
{
	int pri = LOG_KERN|LOG_NOTICE|LOG_FACMASK;
	const char *message;

	/* Don't kill ourself */
	signal(SIGTERM,SIG_IGN);
	signal(SIGHUP,SIG_IGN);

	/* Allow Ctrl-Alt-Del to reboot system. */
#ifndef RB_ENABLE_CAD
#define RB_ENABLE_CAD	0x89abcdef
#endif
	reboot(RB_ENABLE_CAD);

	message = "\nThe system is going down NOW !!";
	syslog(pri, "%s", message);
	printf(bb_shutdown_format, message);

	sync();

	/* Send signals to every process _except_ pid 1 */
	message = "TERM";
	syslog(pri, init_sending_format, message);
	printf(bb_shutdown_format, message);

	kill(-1, SIGTERM);
	sleep(1);
	sync();

	message = "KILL";
	syslog(pri, init_sending_format, message);
	printf(bb_shutdown_format, message);

	kill(-1, SIGKILL);
	sleep(1);

	sync();

	// reboot(magic);

	return 0; /* Shrug */
}

unsigned long get_reboot_magic(const char* cmd)
{
	unsigned long magic;

	if (strncmp(cmd, "shutdown", 8) == 0) {
		magic = LINUX_REBOOT_CMD_POWER_OFF;
	} else if (strncmp(cmd, "reboot", 6) == 0) {
		magic = LINUX_REBOOT_CMD_RESTART;
	} else if (strncmp(cmd, "download", 8) == 0 ||
			strncmp(cmd, "recovery", 8) == 0 ||
			strncmp(cmd, "fastboot", 8) == 0 ||
			strncmp(cmd, "bootloader", 10) == 0) {
		magic = LINUX_REBOOT_CMD_RESTART2;
	} else {
		return -1;
	}
}

void print_usage(int argc, char* argv[])
{
	if (argc > 0) {
		printf("Usage: %s [%s]\n", argv[0],
		 "bootloader, download, fastboot, reboot, recovery, shutdown");
	}
}

int main(int argc, char* argv[])
{
	const char* cmd;
	unsigned long magic;
	int ret;

	if(geteuid() != 0) {
		fprintf(stderr, "Must be run as root.\n");
		exit(EXIT_FAILURE);
	}

	if (argc == 1) {
		magic = LINUX_REBOOT_CMD_RESTART;
		cmd = NULL;
	} else if (argc == 2) {
		cmd = argv[1];
		magic = get_reboot_magic(cmd);
		if (magic == -1) {
			fprintf(stderr, "Unknown command: %s\n", cmd);
			print_usage(argc, argv);
			exit(EXIT_FAILURE);
		}
	} else {
		print_usage(argc, argv);
		exit(EXIT_FAILURE);
	}

	bb_shutdown_system(magic);

	if (magic == LINUX_REBOOT_CMD_RESTART2) {
		ret = syscall(__NR_reboot,
			LINUX_REBOOT_MAGIC1, LINUX_REBOOT_MAGIC2,
			LINUX_REBOOT_CMD_RESTART2, cmd);
	} else {
		reboot(magic);
		ret = 0;
	}

	return ret;
}
