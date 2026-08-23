# PCIe Topology

Source: `lspci` on Kubuntu 24.04

## Discrete GPUs

| BDF     | Device          | Endpoint link (card-internal) | IOMMU group | Path (root port → switch → endpoint)     |
|---------|-----------------|----------------------|-------------|-------------------------------------------|
| 03:00.0 | AMD/ATI 7551    | PCIe 5.0 x16 (32 GT/s) | 17       | 00:01.1 → 01:00.0 → 02:00.0 → **03:00.0** |
| 07:00.0 | AMD/ATI 7551    | PCIe 5.0 x16 (32 GT/s) | 22       | 00:01.3 → 05:00.0 → 06:00.0 → **07:00.0** |

## CPU↔GPU link width (the number that matters)

| Root port | Feeds   | max_link_width | current_link_width | Speed          |
|-----------|---------|----------------|--------------------|----------------|
| 00:01.1   | GPU0    | **x8**         | x8                 | Gen4, 16 GT/s  |
| 00:01.3   | GPU1    | **x8**         | x8                 | Gen4, 16 GT/s  |

Both GPUs sit on separate root ports and separate IOMMU groups, at a symmetric **x8/x8**.

> **Measurement gotcha.** The GPU endpoints (`03:00.0`, `07:00.0`) always report x16 @ 32 GT/s.
> That is the card-internal GPU↔switch link, not the CPU↔GPU link, and reading it as system
> bandwidth is wrong. Read `max_link_width` on the **root port** (`00:01.1` / `00:01.3`) instead.
> `current_link_width` under-reports at idle because ASPM collapses width and speed — measure
> under load (H2D DMA) or use `max_link_width`.

The x8/x8 allocation was restored on 2026-06-14 by moving one NVMe from an M.2 slot on CPU
lanes to a chipset slot; before that, two CPU-lane NVMe drives had cut GPU1 to x4.

## NVMe Storage

| BDF     | Controller                              | Root port |
|---------|-----------------------------------------|-----------|
| 04:00.0 | Phison PS5027-E27T (GOODRAM PX700)      | 00:01.2   |
| 08:00.0 | Phison PS5027-E27T (GOODRAM PX700)      | 00:01.4   |

## Networking

| BDF     | Device                                  | Path                          |
|---------|-----------------------------------------|-------------------------------|
| 0e:00.0 | MediaTek MT7922 WiFi 6E                 | chipset switch → 0d:05.0      |
| 0f:00.0 | Intel I226-V 2.5GbE                     | chipset switch → 0d:06.0      |
| 10:00.0 | Aquantia AQC113CS 10GbE                 | chipset switch → 0d:08.0      |

## Chipset & Peripherals

| BDF     | Device                                  | Notes                         |
|---------|-----------------------------------------|-------------------------------|
| 12:00.0 | AMD USB controller                      | chipset USB                   |
| 13:00.0 | AMD 600 Series SATA                     | chipset SATA                  |
| 14:00.0 | AMD USB controller                      | chipset USB                   |
| 15:00.0 | AMD 600 Series SATA                     | chipset SATA                  |
| 16:00.0 | ASMedia 2421 → 2423 hub                 | front-panel USB hub           |
| 7c:00.0 | ASMedia 2426 USB                        | ASMedia USB (rear?)           |
| 7d:00.0 | ASMedia 2425 USB                        | ASMedia USB                   |

## Integrated GPU & SoC

| BDF     | Device                                  | Notes                         |
|---------|-----------------------------------------|-------------------------------|
| 7e:00.0 | AMD/ATI 13c0 (Raphael iGPU)            | integrated RDNA 2             |
| 7e:00.1 | Rembrandt HD Audio                      | HDMI/DP audio (iGPU)         |
| 7e:00.2 | AMD PSP/CCP                             | platform security processor   |
| 7e:00.3 | AMD USB                                 | SoC USB                      |
| 7e:00.4 | AMD USB                                 | SoC USB                      |
| 7e:00.6 | AMD HD Audio                            | onboard audio codec           |
| 7f:00.0 | AMD USB                                 | SoC USB                      |

## Verification checklist

- [x] Both discrete GPUs on separate root ports (00:01.1, 00:01.3)
- [x] CPU↔GPU link width verified on the **root ports**: symmetric x8/x8 (Gen4, 16 GT/s)
      — the x16 @ 32 GT/s shown for the endpoints above is the card-internal link
- [x] IOMMU groups confirmed separate (group 17, group 22)
