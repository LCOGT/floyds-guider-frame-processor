# floyds-guider-frame-processor
Processor for FLOYDS guider frames

## Deployment
The FLOYDS guider frame processor is run at site and managed by Puppet.

### Updating site deployment
To update the deployment at site once changes are merged to master:

1. ssh onto the site machine you which to update

2. As root:
`rm -rf /home/eng/floyds-guider-frame-processor{,-env} && puppet agent --test`

This will trigger puppet to pull down the latest changes and re-install the
required modules.
