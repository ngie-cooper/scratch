#!/usr/bin/env python3
"""
Copyright (c) 2012-2019, Enji Cooper
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

- Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
- Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import shlex
import subprocess
import time


SNAPSHOT_SEPARATOR = "@"
ZFS = "/sbin/zfs"


def snapshot_name(vdev, date_format):
    """Create a properly formatted snapshot name

    :Parameters:
        vdev:        name of a vdev to take a snapshot with.
        date_format: strftime(3) compatible date format to assign to the
                     snapshot.
    """
    return "%s%s%s" % (vdev, SNAPSHOT_SEPARATOR, date_format)


def zfs(arg_str):
    """A command through zfs(8).

    :Parameters:
        arg_str: a flat string with a list of arguments to pass to zfs(8),
                 e.g. -t snapshot.

    :Returns:
        The output from zfs(8).
    """
    output = subprocess.check_output([ZFS] + shlex.split(arg_str))
    try:
        return str(output, encoding="utf-8")
    except TypeError:
        return output


def create_snapshot(vdev, date_format):
    """Create a snapshot for a vdev with a given date format.

    :Parameters:
        vdev:        name of a vdev to take a snapshot with.
        date_format: strftime(3) compatible date format to assign to the
                     snapshot.
    """

    zfs("snapshot %s" % (snapshot_name(vdev, date_format)))


def destroy_snapshot(snapshot):
    """Destroy a snapshot

    :Parameters:
        snapshot: name of the snapshot to destroy.
    """

    zfs("destroy %s" % (snapshot))


def list_vdevs():
    """Return all vdevs.

    :Raises:
        ValueError: no vdevs could be found.

    :Returns:
        A list of available vdevs.
    """

    vdevs = zfs("list -H -t filesystem,volume -o name").split()
    if not vdevs:
        raise ValueError("no vdevs found on system")
    return vdevs


def list_snapshots(vdev, recursive=True):
    """Get a list of ZFS snapshots for a given vdev

    :Parameters:
        vdev:      a vdev to grab snapshots for.
        recursive: list snapshot(s) for the parent and child vdevs.

    :Returns:
        A list of zero or more snapshots
    """

    recursive_flag = " -r" if recursive else ""

    return zfs("list -H -t snapshot %s -o name %s" % (recursive_flag, vdev)).splitlines()


def is_destroyable_snapshot(vdev, cutoff, date_format, snapshot):
    """Take a snapshot string, unmarshall the date, and determine if it's
       eligible for destruction.

    :Parameters:
        vdev:        name of the vdev to execute the snapshotting policy
                     (creation/deletion) on.
        cutoff:      any snapshots created before this time are nuked. This
                     is a tuple, resembling a `time.struct_tm` object.
        date_format: a strftime(3) compatible date format to look for/destroy
                     snapshots with.
        snapshot:    snapshot name.

    :Returns:
        True if the snapshot is out of date; False otherwise.
    """

    snapshot_formatted = snapshot_name(vdev, date_format)
    try:
        snapshot_time = time.strptime(snapshot, snapshot_formatted)
    except ValueError:
        # Date format does not match
        return False
    return snapshot_time < time.struct_time(cutoff)


def execute_snapshot_policy(vdev, now, cutoff, date_format, recursive=True):
    """Execute snapshot policy on a vdev -- destroying as necessary and
       creating a snapshot at the end.

    :Parameters:
        vdev:        name of the vdev to execute the snapshotting policy
                     (creation/deletion) on.
        now:         new time to snapshot against. This should be the time
                     that the script execution was started (e.g. a stable
                     value).
        cutoff:      any snapshots created before this time are nuked. This
                     is a tuple, resembling a `time.struct_tm` object.
        date_format: a strftime(3) compatible date format to look for/destroy
                     snapshots with.
        recursive:   execute zfs snapshot create recursively.
    """

    snapshots = list_snapshots(vdev, recursive=recursive)

    expired_snapshots = [
        snapshot
        for snapshot in snapshots
        if is_destroyable_snapshot(vdev, cutoff, date_format, snapshot)
    ]
    for snapshot in sorted(expired_snapshots, reverse=True):
        # Destroy snapshots as needed, reverse order so the snapshots will
        # be destroyed in order.
        destroy_snapshot(snapshot)

    create_snapshot(vdev, time.strftime(date_format, now))
